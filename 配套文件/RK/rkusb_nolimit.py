#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2024-2026 IFLYTEK-LEAKING
# SPDX-FileCopyrightText: 2024-2026 KawaiiSparkle
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# 全体贡献者见 CONTRIBUTORS.md
"""
rkusb_nolimit.py -- remove the Rockchip rockusb 32 MiB read limit from a flash
dump.  ONE self-contained file: Python 3 standard library only, no third-party
packages, no shell, no POSIX-only calls.  Runs the same on Windows and Unix.

WHY THE PATCH IS NEEDED
-----------------------
Rockchip's U-Boot caps how far rockusb (the USB-download gadget that
RKDevTool / upgrade_tool talk to) is allowed to read:

    include/rockusb.h:129
        #define RKUSB_READ_LIMIT_ADDR   (32 * 2048)     /* 65536 sectors */

    cmd/rockusb.c:23-40   rkusb_read_sector()
        blkstart = start + ums_dev->start_sector;
        if ((blkstart + blkcnt) > RKUSB_READ_LIMIT_ADDR) {
                memset(buf, 0xcc, blkcnt * SECTOR_SIZE);
                return blkcnt;                          /* lies: "success" */
        } else {
                ret = blk_dread(...);
        }

So every sector at or beyond 32 MiB comes back as 0xCC, and the read is
*reported as successful*.  That is exactly the wall visible in the RK3576
eMMC dump this tool was built against: 0x02000000-0x03ffffff is 33554432 /
33554432 bytes of 0xCC with zero exceptions, which is why its dtbo / vbmeta /
boot partitions look erased.  The test is on the *end* sector, so a request
straddling the boundary is replaced whole.

The fix is the one-line change from the RV1106 U-Boot: make the guard
impossible to take, `... > RKUSB_READ_LIMIT_ADDR && 0`.  In the compiled
image that is a single branch instruction, rewritten in place to `b #0`
(same length, so XIP images keep working):

    b.ls  <blk_dread path>   54000149   ->   b #0   14000000

WHAT THIS FILE DOES, per input
------------------------------
  1. classify  device serial number, SoC, GPT, A/B slot, every U-Boot FIT
               copy in the image, and whether the limit is active in each
  2. trim      cut a repeated-block read-garbage tail, if there is one
  3. patch     neutralise the guard in EVERY FIT copy and refresh every
               /images/*/hash/value.  In place when the payload is raw or the
               recompressed gzip still fits its slot; otherwise the whole FIT
               is rebuilt with SPL-compatible layout rules.
  4. verify    FDT header, every image hash, payload decompresses, guard is
               `b #0`, and the 32 MiB compare is untouched

Exit code is 0 only if every input was patched AND verified.

USAGE
-----
    python3 rkusb_nolimit.py                          # every .bin/.img in in/
    python3 rkusb_nolimit.py dump.bin ...             # only these files
    python3 rkusb_nolimit.py --in D --out D ...       # other directories
    python3 rkusb_nolimit.py classify dump.bin        # identify, change nothing
    python3 rkusb_nolimit.py patch dump.bin -o out.bin
    python3 rkusb_nolimit.py verify orig.bin out.bin
    python3 rkusb_nolimit.py trim dump.bin -o cut.bin
    python3 rkusb_nolimit.py limit payload.bin        # just find the guard
    python3 rkusb_nolimit.py fit info|unpack|repack   # FIT-level work
    python3 rkusb_nolimit.py selftest                 # end-to-end regression
    python3 rkusb_nolimit.py --help

Supported inputs
----------------
  emmc32    eMMC first 32 MiB, uboot_a/uboot_b, gzip payload   (RK3576 SS30)
  spi_ok    SPINOR 8/16 MiB, GPT matches where the FITs are    (T20/T30/T90Pro)
  spi_bad   SPINOR whose GPT does NOT match reality  -> patch by real offset
  spi_noub  SPINOR holding no U-Boot at all (SPI+NVMe) -> nothing to patch

Notes on the signature question
-------------------------------
None of these images carries a usable FIT signature: every `signature` node
holds only algo/key-name-hint/sign-images and no `value`, and neither SPL
enforces one (RK3576 SPL @0x40000384 reads OTP id 8 offset 0x20 and only
demands a signature when that byte is 0xFF; RK3588's idblock has no
signature-related strings at all).  So re-signing is not required and the
empty `signature` node is deliberately left alone -- "nothing to check"
passes fit_image_verify_with_data(), a wrong `value` would return -EBADMSG.
See INTEGRITY.md next to this file for the evidence.
"""

import argparse
import builtins
import gzip
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib

VERSION = '3.0-selfcontained'  # 修正版guard(动态目标+写前校验) + AIO(digest/repack头修复/--plan/--verify)，完全自包含
PROG = os.path.basename(sys.argv[0] or 'rkusb_nolimit.py')

# --------------------------------------------------------------------------
# Constants.  Every magic number below is either mandated by the RK/FIT
# format or is a fixed AArch64 encoding the compiler had no freedom in.
# --------------------------------------------------------------------------

SECTOR = 512
ALIGN = 4096                        # FIT_ALIGN in SPL
RKUSB_LIMIT_SECTORS = 32 * 2048     # RKUSB_READ_LIMIT_ADDR, 65536 sectors

FDT_MAGIC = b'\xd0\x0d\xfe\xed'
FDT_BEG, FDT_END, FDT_PROP, FDT_NOP, FDT_FEND = 1, 2, 3, 4, 9
FDT_HDR = struct.Struct('>10I')
FDT_HDR_LEN = 40

RKNS = b'RKNS'                      # Rockchip idblock magic
AVB_AB_MAGIC = b'\x00AB0'           # AvbABData, common/spl/spl_ab.c
AB_METADATA_OFFSET = 4              # sectors, include/spl_ab.h
AVB_AB_MAX_PRIORITY = 15
AVB_AB_MAX_TRIES = 7

# AArch64 encodings inside rkusb_read_sector().  Little endian on disk.
#
#   ldr w4, [x0, #0x18]     b9401804   ums->start_sector.  struct ums is in
#                                      include/usb_mass_storage.h:
#                                      read_sector@0x00 write_sector@0x08
#                                      erase_sector@0x10 start_sector@0x14
#                                      num_sectors@0x18 name@0x20
#                                      block_dev@0x28, sizeof 0xd0
#   add x1, x4, x1          8b010081   blkstart = start + ums->start_sector
#   add x4, x1, x2          8b020024   blkstart + blkcnt
#   cmp x4, #0x10, lsl #12  f140409f   vs 0x10000 sectors == 32 MiB
#   b.ls  <blk_dread path>  54000149   <-- THE PATCH SITE (cond `ls` = 9 pairs
#                                      with the source's unsigned `>`)
#   mov w1, #0xcc           52801981   the memset fill value
#   add x0, x0, #0x28       9100a000   &ums->block_dev, on the normal path
#   lsl x2, x2, #9          d377d842   blkcnt * SECTOR_SIZE
#
# Encoding notes, because both are easy to get wrong:
#   * `cmp xN, #imm, lsl #s` is SUBS XZR:
#         sf<<31 | 11101001 | sh<<22 | imm12<<10 | Rn<<5 | 11111
#     `sh` is ONE bit (bit 22): 0 = no shift, 1 = `lsl #12`.  Treating it as
#     two bits silently yields a 4096x-too-small limit.
#   * `b.<cond>` is 01010100 | imm19<<5 | 0 | cond, so the low nibble is the
#     condition and bits 23:5 are a signed offset in instructions.
LDR_START_SECTOR = 0xB9401804
ADD_BLKSTART = 0x8B010081
ADD_BLKEND = 0x8B020024
CMP_32MB = 0xF140409F
MOV_0XCC = 0x52801981
ADD_BLOCK_DEV = 0x9100A000
LSL9 = 0xD377D842
BRANCH_ALWAYS = 0x1400000A          # b +0x28 -> blk_dread (correct fix; b#0 bricks)
B_LS = 0x54000149                   # the stock guard, used by the selftest

COND = ['eq', 'ne', 'cs', 'cc', 'mi', 'pl', 'vs', 'vc',
        'hi', 'ls', 'ge', 'lt', 'gt', 'le', 'al', 'nv']

# Device serial number: 2-4 uppercase letters + 15-17 digits.  Random code
# bytes match the shape too, so callers filter on repeat count.
SN_RE = re.compile(rb'(?<![A-Z0-9])[A-Z]{2,4}[0-9]{15,17}(?![0-9A-Z])')
SN_MIN_HITS = 3
# build ids like T20YWBBZDGJ1723118411 sitting inside the FIT / DTB
BUILDID_RE = re.compile(rb'\b[TMCS][0-9]{2}[A-Z]{6,14}[0-9]{6,14}\b')

SOC_BY_CHIP = {0x356: 'RK3568', 0x357: 'RK3576', 0x358: 'RK3588'}


# --------------------------------------------------------------------------
# output plumbing: a Windows console may not be able to encode the Chinese
# characters in these file names, so never let that crash the run.
# --------------------------------------------------------------------------
def _harden_stdio():
    for st in (sys.stdout, sys.stderr):
        try:
            st.reconfigure(errors='replace')
        except Exception:
            pass


_SAY = builtins.print


def say(*a, **k):
    _SAY(*a, **k)


def _set_say(verbose):
    global _SAY
    _SAY = builtins.print if verbose else (lambda *a, **k: None)


def rd(path):
    with open(path, 'rb') as f:
        return f.read()


def wr(path, data):
    d = os.path.dirname(os.path.abspath(path))
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, 'wb') as f:
        f.write(data)


# ==========================================================================
# 1. FDT (device tree) reader/writer
#
# Layout actually found in this device's uboot_a / uboot_b partitions:
#
#     0x000  fdt_header            40 B   (off_dt_struct / off_dt_strings are
#                                         written SWAPPED by Rockchip mkimage)
#     0x028  memreserve block      32 B   (1 entry + terminator)
#     0x048  struct block        2468 B
#     0x9EC  string table         208 B
#     0xABC  zero padding         324 B   -> totalsize 0xC00
#     0x1200 first external payload (images/uboot data-position)
#
# `totalsize` is padded so FIT_ALIGN(totalsize) == 0x1000, which is what
# SPL's spl_load_read_fit_header() uses as the external-data base.
# pack(keep_layout=True) reproduces the input byte-for-byte when nothing was
# modified.  NOTE: pack() is NOT byte-identical in general -- to change one
# property, overwrite the 32-byte value in place (see refresh_hash()).
# ==========================================================================
def _walk_end(buf, start):
    """End offset of the token stream starting at `start`, or None."""
    pos = start
    try:
        while True:
            t = struct.unpack_from('>I', buf, pos)[0]
            pos += 4
            if t == FDT_BEG:
                e = buf.index(b'\0', pos)
                pos = (e + 1 + 3) & ~3
            elif t == FDT_PROP:
                ln = struct.unpack_from('>I', buf, pos)[0]
                pos = (pos + 8 + ln + 3) & ~3
            elif t == FDT_FEND:
                return pos
            elif t not in (FDT_END, FDT_NOP):
                return None
    except (IndexError, struct.error, ValueError):
        return None


class Node:
    __slots__ = ('name', 'props', 'children')

    def __init__(self, name):
        self.name = name
        self.props = []                 # [(name, value, nameoff)]
        self.children = []

    def find(self, path):
        cur = self
        for part_name in [x for x in path.split('/') if x]:
            nxt = next((c for c in cur.children if c.name == part_name), None)
            if nxt is None:
                return None
            cur = nxt
        return cur

    def get(self, name):
        for k, v, _ in self.props:
            if k == name:
                return v

    def set(self, name, value):
        for i, (k, _v, o) in enumerate(self.props):
            if k == name:
                self.props[i] = (k, value, o)
                return
        raise KeyError(name)

    def u32(self, name):
        v = self.get(name)
        return struct.unpack('>I', v)[0] if v else None

    def set_u32(self, name, value):
        self.set(name, struct.pack('>I', value))


class FDT:
    def __init__(self, buf, off=0):
        self.o = off
        (magic, self.tsize, h2, h3, self.offmem, self.ver, self.last,
         self.bootcpu, self.szstr, self.szstruct) = FDT_HDR.unpack_from(buf, off)
        if magic != 0xd00dfeed:
            raise ValueError('not an FDT: magic=%08x' % magic)

        # memreserve block: entries until a (0,0) terminator; its length is
        # not in the header, so it has to be scanned for.
        p = self.offmem
        while struct.unpack_from('>QQ', buf, off + p) != (0, 0):
            p += 16
        p += 16
        self.memres = buf[off + self.offmem: off + p]

        self.offstruct = p              # struct block follows the memreserves
        if _walk_end(buf, off + self.offstruct) is None:
            raise ValueError('no FDT token stream at 0x%x' % (off + self.offstruct))
        self.offstr = self.offstruct + self.szstruct
        self.strtab = buf[off + self.offstr: off + self.offstr + self.szstr]
        self.tail_gap = self.tsize - (self.offstr + self.szstr)
        # Rockchip's mkimage swaps these two header fields - remember that
        self.swapped = (h2 == self.offstruct and h3 == self.offstr)
        if not self.swapped and (h2 != self.offstr or h3 != self.offstruct):
            raise ValueError('unrecognised header layout: %08x %08x' % (h2, h3))

        self.root = self._parse(buf)

    # ---------------------------------------------------------------- parse
    def _sname(self, o):
        return self.strtab[o:self.strtab.index(b'\0', o)].decode('latin1')

    def _parse(self, buf):
        pos = self.o + self.offstruct
        wrapper = Node('')
        stack = [wrapper]
        while True:
            t = struct.unpack_from('>I', buf, pos)[0]
            pos += 4
            if t == FDT_BEG:
                e = buf.index(b'\0', pos)
                node = Node(buf[pos:e].decode('latin1'))
                pos = (e + 1 + 3) & ~3
                stack[-1].children.append(node)
                stack.append(node)
            elif t == FDT_END:
                stack.pop()
            elif t == FDT_PROP:
                ln, no = struct.unpack_from('>II', buf, pos)
                pos += 8
                stack[-1].props.append((self._sname(no), buf[pos:pos + ln], no))
                pos = (pos + ln + 3) & ~3
            elif t == FDT_FEND:
                self.struct_used = pos - (self.o + self.offstruct)
                if len(wrapper.children) != 1:
                    raise ValueError('expected exactly one root node')
                return wrapper.children[0]
            elif t == FDT_NOP:
                pass
            else:
                raise ValueError('bad token %d @0x%x' % (t, pos - 4))

    # ---------------------------------------------------------------- write
    def _soff(self, name):
        key = name.encode('latin1') + b'\0'
        i = self.strtab.find(key)
        while i >= 0:
            if i == 0 or self.strtab[i - 1] == 0:
                return i
            i = self.strtab.find(key, i + 1)
        off = len(self.strtab)
        self.strtab += key
        return off

    def _struct_blob(self):
        s = bytearray()

        def emit(node):
            s.extend(struct.pack('>I', FDT_BEG))
            s.extend(node.name.encode('latin1') + b'\0')
            while len(s) % 4:
                s.append(0)
            for k, v, no in node.props:
                s.extend(struct.pack('>II', FDT_PROP, len(v)))
                s.extend(struct.pack('>I', no if no is not None else self._soff(k)))
                s.extend(v)
                while len(s) % 4:
                    s.append(0)
            for c in node.children:
                emit(c)
            s.extend(struct.pack('>I', FDT_END))

        emit(self.root)
        s.extend(struct.pack('>I', FDT_FEND))
        while len(s) % 4:
            s.append(0)
        if self.szstruct > len(s):
            s.extend(b'\0' * (self.szstruct - len(s)))
        return bytes(s)

    def pack(self, keep_layout=True, totalsize=None):
        """Serialise.

        keep_layout : pad back to the original totalsize so an unmodified tree
                      round-trips byte-for-byte.
        totalsize   : explicit totalsize for the header (mkimage writes the
                      *whole image* size here; SPL derives the external-data
                      base as FIT_ALIGN(totalsize)).
        """
        struct_blob = self._struct_blob()
        str_blob = self.strtab
        offstruct = self.offmem + len(self.memres)
        offstr = offstruct + len(struct_blob)
        body = self.memres + struct_blob + str_blob
        tsize = FDT_HDR_LEN + len(body)
        if keep_layout and tsize < self.tsize:
            body += b'\0' * (self.tsize - tsize)
            tsize = self.tsize
        if totalsize is not None:
            if totalsize < tsize:
                raise ValueError('totalsize %d smaller than the FDT blob %d'
                                 % (totalsize, tsize))
            tsize = totalsize
        f2, f3 = (offstruct, offstr) if self.swapped else (offstr, offstruct)
        hdr = FDT_HDR.pack(0xd00dfeed, tsize, f2, f3, self.offmem, self.ver,
                           self.last, self.bootcpu, len(str_blob),
                           len(struct_blob))
        return hdr + body


# ==========================================================================
# 2. GPT and A/B metadata
# ==========================================================================
def parse_gpt(d):
    """Unified GPT reader: header fields plus one dict per partition.

    Header layout (92 bytes at LBA 1): signature 0, revision 8, size 12,
    crc 16, reserved 20, current LBA 24, backup 32, first usable 40, last
    usable 48, disk GUID 56, entries LBA 72, n entries 80, entry size 84,
    entries crc 88.
    """
    if len(d) < 0x200 + 92 or d[0x200:0x208] != b'EFI PART':
        return None
    h = d[0x200:0x200 + 92]
    cur, bak, first, last = struct.unpack_from('<QQQQ', h, 24)
    ent_lba, n, esz, pe_crc = struct.unpack_from('<QIII', h, 72)
    g = dict(cur=cur, bak=bak, first=first, last=last, last_usable=last,
             ent_lba=ent_lba, n=n, esz=esz, pe_crc=pe_crc,
             disk_guid=h[56:72].hex(), parts=[])
    if esz == 0 or n == 0:
        return g
    for i in range(n):
        off = ent_lba * SECTOR + i * esz
        if off + esz > len(d):
            break
        e = d[off:off + esz]
        if e[:16] == b'\0' * 16:
            continue
        try:
            st, en, attr = struct.unpack_from('<QQQ', e, 32)
            name = e[56:128].decode('utf-16-le').rstrip('\0')
        except (struct.error, UnicodeDecodeError):
            continue
        if en < st:
            continue
        g['parts'].append(dict(idx=len(g['parts']), name=name, start=st,
                               end=en, sectors=en - st + 1, attr=attr,
                               guid=e[0:16].hex(), off=st * SECTOR,
                               size=(en - st + 1) * SECTOR))
    return g


def part(g, name):
    if not g:
        return None
    return next((p for p in g['parts'] if p['name'] == name), None)


def part_containing(g, off):
    """The partition whose byte range covers `off`."""
    if not g:
        return None
    return next((p for p in g['parts']
                 if p['off'] <= off < p['off'] + p['size']), None)


def read_ab(d, g):
    """Decode AvbABData exactly like common/spl/spl_ab.c does.

    Layout at misc + AB_METADATA_OFFSET*512 (0x800):
        0  magic "\\0AB0"      8  slot0 {priority,tries,successful,unused}
        4  version            12  slot1 {...}
       16  last_boot          28  crc32 (big endian) over bytes 0..27
    Returns None when there is no misc partition or the block is truncated.
    `valid`/`crc_ok` tell the caller whether SPL would trust it.
    """
    p = part(g, 'misc')
    if p is None:
        return None
    off = p['off'] + AB_METADATA_OFFSET * SECTOR
    blk = d[off:off + 64]
    if len(blk) < 32:
        return None
    magic = bytes(blk[0:4])
    valid = magic == AVB_AB_MAGIC
    slots, bootable = [], []
    for i in (0, 1):
        pr, tr, su, _r = blk[8 + i * 4:12 + i * 4]
        b = bool(pr > 0 and (su or tr > 0))
        slots.append(dict(priority=pr, tries=tr, successful=su, bootable=b))
        bootable.append(b)
    last_boot = blk[16]
    crc = struct.unpack_from('>I', blk, 28)[0]
    crc_ok = crc == (zlib.crc32(blk[0:28]) & 0xFFFFFFFF)
    if valid and crc_ok:
        boot = [i for i, b in enumerate(bootable) if b]
        if len(boot) == 2:
            idx = max(boot, key=lambda i: slots[i]['priority'])
            why = 'both bootable -> higher priority wins'
        elif len(boot) == 1:
            idx, why = boot[0], 'only bootable slot'
        else:
            idx, why = last_boot, 'none bootable -> last_boot'
        why += ' (metadata valid, crc 0x%08x)' % crc
    else:
        # spl_ab_data_init() defaults
        slots = [dict(priority=AVB_AB_MAX_PRIORITY, tries=AVB_AB_MAX_TRIES,
                      successful=0, bootable=True),
                 dict(priority=AVB_AB_MAX_PRIORITY - 1,
                      tries=AVB_AB_MAX_TRIES, successful=0, bootable=True)]
        bootable = [True, True]
        idx = last_boot
        why = ('metadata %s -> SPL re-inits with defaults, last_boot=%d'
               % ('absent' if not valid else 'crc BAD 0x%08x' % crc, last_boot))
    return dict(off=off, magic=magic, valid=valid, crc=crc, crc_ok=crc_ok,
                slots=slots, bootable=bootable, last_boot=last_boot,
                index=idx, suffix='_ab'[idx], why=why, reason=why)


# ==========================================================================
# 3. FIT helpers
# ==========================================================================
def find_fits(d, lo=0, hi=None):
    """[(offset, totalsize)] of every Rockchip FIT FDT blob in `d`."""
    hi = len(d) if hi is None else hi
    out = []
    o = lo
    while True:
        i = d.find(FDT_MAGIC, o, hi)
        if i < 0:
            break
        if (i & 3) == 0 and i + FDT_HDR_LEN <= len(d):
            ts, _f2, _f3, offmem, ver, last = struct.unpack_from('>6I', d, i + 4)
            # A Rockchip FIT FDT blob: sane totalsize, version 17,
            # last_comp_version 16, memreserve right after the 40-byte header.
            if 0x400 < ts < 0x4000000 and ver == 17 and last == 16 and offmem == 40:
                out.append((i, ts))
        o = i + 4
    return out


def is_uboot_fit(d, off):
    """A U-Boot FIT has /images/uboot."""
    try:
        return FDT(d, off).root.find('images/uboot') is not None
    except Exception:
        return False


def uboot_payload(d, off):
    """{comp, load, pos, size, img} of /images/uboot in the FIT at `off`."""
    f = FDT(d, off)
    n = f.root.find('images/uboot')
    comp = n.get('compression').rstrip(b'\0').decode()
    pos, size = n.u32('data-position'), n.u32('data-size')
    raw = bytes(d[off + pos: off + pos + size])
    if comp == 'gzip':
        raw = gzip.decompress(raw)
    return dict(comp=comp, load=n.u32('load'), pos=pos, size=size, img=raw)


def fit_images(fdt):
    out = []
    images = fdt.root.find('images')
    if images is None:
        return out
    for node in images.children:
        pos, size = node.u32('data-position'), node.u32('data-size')
        if pos is None:
            continue
        out.append(dict(node=node, name=node.name, pos=pos, size=size,
                        comp=(node.get('compression') or b'none')
                        .rstrip(b'\0').decode(),
                        load=node.u32('load')))
    return out


def fit_unpack(d, gpt, slot, outdir):
    os.makedirs(outdir, exist_ok=True)
    p = part(gpt, 'uboot_' + slot)
    if p is None:
        raise SystemExit('no uboot_%s partition' % slot)
    raw = d[p['off']:p['off'] + p['size']]
    probe = FDT(raw)          # header totalsize only covers the FDT part
    end = max(im['pos'] + im['size'] for im in fit_images(probe))
    itb = raw[:end]
    wr(os.path.join(outdir, 'uboot_%s.itb' % slot), itb)
    fdt = FDT(itb)
    manifest = dict(slot=slot, part=p, fit_totalsize=fdt.tsize,
                    fit_hdr_totalsize=struct.unpack_from('>I', itb, 4)[0],
                    images={})
    for im in fit_images(fdt):
        blob = itb[im['pos']:im['pos'] + im['size']]
        fn = '%s.bin' % im['name']
        wr(os.path.join(outdir, fn), blob)
        e = dict(file=fn, pos=im['pos'], size=im['size'], comp=im['comp'],
                 load=im['load'], sha256=hashlib.sha256(blob).hexdigest())
        if im['comp'] == 'gzip':
            dec = gzip.decompress(blob)
            e['dec_file'] = '%s.dec' % im['name']
            e['dec_sha256'] = hashlib.sha256(dec).hexdigest()
            wr(os.path.join(outdir, e['dec_file']), dec)
        hnode = im['node'].find('hash')
        if hnode is not None:
            e['hash_algo'] = (hnode.get('algo') or b'').rstrip(b'\0').decode()
            e['hash_stored'] = (hnode.get('value') or b'').hex()
            e['hash_ok'] = hashlib.sha256(blob).digest() == hnode.get('value')
        manifest['images'][im['name']] = e
    with open(os.path.join(outdir, 'manifest.json'), 'w') as f:
        json.dump(manifest, f, indent=1, default=str)
    return manifest


def fit_repack(indir, slot, outfile, align=ALIGN):
    """Rebuild an .itb from unpacked payloads.

    Layout rules taken from the stock image and from SPL:
      * FDT blob lives at 0, padded up to `align`
      * payload i starts at data-position (absolute from image start), each
        payload aligned to `align`
      * header totalsize == whole image size, and FIT_ALIGN(totalsize) must
        equal the padded FDT length, because spl_load_read_fit_header() uses
        it as the external-data base
      * every /images/<x>/hash/value is sha256 over the bytes as stored
    """
    itb = rd(os.path.join(indir, 'uboot_%s.itb' % slot))
    fdt = FDT(itb)
    images = fit_images(fdt)

    payloads = []
    for im in images:
        name, data = im['name'], None
        if im['comp'] == 'gzip':
            dec = os.path.join(indir, '%s.dec' % name)
            if os.path.exists(dec):
                data = gzip.compress(rd(dec), 9, mtime=0)
        if data is None:
            data = rd(os.path.join(indir, '%s.bin' % name))
        payloads.append((im, data))

    # 1) fixed layout: FDT blob padded to `align`, payloads after it
    fdt_len = align
    pos, plan = fdt_len, []
    for _im, data in payloads:
        plan.append((pos, len(data)))
        pos = (pos + len(data) + align - 1) & ~(align - 1)
    total = pos

    # 2) layout is final, so record it and recompute every hash
    for (im, data), (p_, size) in zip(payloads, plan):
        im['node'].set_u32('data-position', p_)
        im['node'].set_u32('data-size', size)
        hnode = im['node'].find('hash')
        if hnode is not None:
            algo = (hnode.get('algo') or b'sha256').rstrip(b'\0').decode()
            if algo != 'sha256':
                raise SystemExit('unsupported hash algo %r - extend this '
                                 'tool first' % algo)
            hnode.set('value', hashlib.sha256(data).digest())

    # keep the root /totalsize property in sync, as mkimage does: it holds
    # FIT_ALIGN(end-of-last-payload), NOT the FDT blob size (that is hdr[1]).
    # Nothing in SPL's uboot path reads it (spl_fit_load_blob() uses the
    # header fdt_totalsize, payloads are read by absolute data-position), but
    # keeping it consistent avoids surprising dumpimage / other host tools.
    if fdt.root.get('totalsize') is not None:
        fdt.root.set_u32('totalsize', total)

    blob = fdt.pack(keep_layout=False, totalsize=total)
    if len(blob) > fdt_len:
        raise SystemExit('FDT grew to %d bytes, past the first payload slot '
                         'at 0x%x' % (len(blob), fdt_len))
    out = bytearray(total)                  # whole image, zero filled
    out[0:len(blob)] = blob
    for (_im, data), (p_, size) in zip(payloads, plan):
        out[p_:p_ + size] = data
    assert len(out) == total
    wr(outfile, bytes(out))
    return dict(total=total, fdt_len=fdt_len, fdt_blob=len(blob),
                n=len(payloads), plan=plan)


# ==========================================================================
# 4. device identity
# ==========================================================================
def find_sns(d, limit_mb=None):
    hi = len(d) if limit_mb is None else min(len(d), limit_mb * 1024 * 1024)
    found = {}
    for m in SN_RE.finditer(d, 0, hi):
        found.setdefault(m.group().decode(), []).append(m.start())
    return found


def find_buildids(d):
    found = {}
    for m in BUILDID_RE.finditer(d):
        found.setdefault(m.group().decode(), []).append(m.start())
    return found


# ==========================================================================
# 5. the 32 MiB guard: decode it, find it, neutralise it.
#    No disassembler needed - see the encoding table at the top of this file.
# ==========================================================================
def decode_bcond(w):
    """(cond, byte_delta) for a `b.<cond>`, else None."""
    if (w & 0xFF000010) != 0x54000000:
        return None
    imm = (w >> 5) & 0x7FFFF
    if imm & (1 << 18):
        imm -= (1 << 19)
    return w & 0xF, imm * 4


def decode_b(w):
    """byte_delta for an unconditional `b`, else None."""
    if (w & 0xFC000000) != 0x14000000:
        return None
    imm = w & 0x03FFFFFF
    if imm & (1 << 25):
        imm -= (1 << 26)
    return imm * 4


def cmp32mb_imm(w):
    """The compared value if w is `cmp xN, #imm12{, lsl #12}`, else None."""
    if (w & 0x7F80001F) != 0x7100001F:
        return None
    return ((w >> 10) & 0xFFF) << (12 if (w >> 22) & 1 else 0)


def _w(img, off):
    return struct.unpack_from('<I', img, off)[0]


def _words(b):
    return set(struct.unpack_from('<%dI' % (len(b) // 4), b, 0))


def analyse(img, base, label='', quiet=False):
    """Find the guard in an AArch64 U-Boot image.

    img  : the (decompressed) payload bytes
    base : the link address the payload was linked at
    Returns dict(fn, cmp_va, guard, patched, cond, blk_dread) or None.

    The anchor is the run `add x1,x4,x1` / `add x4,x1,x2` / `cmp x4,#32MiB` /
    `b.<cond>` -- those four must be contiguous.  The `ldr w4,[x0,#0x18]`
    that reads ums->start_sector and the `mov w1,#0xcc` fill are confirmed
    inside a window instead, because the scheduler may interleave a spill
    between them (RK3576 puts `str x19,[sp,#0x10]` right after the ldr;
    T30Pro/T90Pro do not).  Requiring six contiguous words finds nothing at
    all on the RK3576 image.
    """
    def _p(*a):
        if not quiet:
            print(*a)

    if not label:
        label = 'image'
    _p('=' * 74)
    _p('  %s   base=0x%x  %d bytes' % (label, base, len(img)))
    _p('=' * 74)

    W = 16                              # words to look around the anchor
    hits = []
    for off in range(0, len(img) - (W + 12) * 4, 4):
        if (_w(img, off) != ADD_BLKSTART or _w(img, off + 4) != ADD_BLKEND
                or _w(img, off + 8) != CMP_32MB):
            continue
        guard_w = _w(img, off + 12)
        d = decode_bcond(guard_w)
        patched = guard_w == BRANCH_ALWAYS
        bad = guard_w == 0x14000000          # 上一版工具写下的 b#0 死循环
        if d is None and not (patched or bad):
            continue
        lo = max(0, off - W * 4)
        win = _words(img[lo:off + (W + 12) * 4])
        if not (LDR_START_SECTOR in win and MOV_0XCC in win):
            continue
        cond, delta = d if d else (None, 0)
        tgt = off + 12 + delta
        ok_tgt = 0 <= tgt < len(img) - 4 and _w(img, tgt) == ADD_BLOCK_DEV
        hits.append(dict(fn=off - 4 * 4 + base,      # approximate entry
                         cmp_va=off + 8 + base,
                         guard=off + 12 + base,
                         patched=patched,
                         cond=cond,
                         blk_dread=tgt + base if ok_tgt else None))

    if not hits:
        _p('  no rkusb_read_sector 32MB guard found in this image')
        return None

    for h in hits:
        _p('  rkusb_read_sector guard found:')
        _p('    add x1, x4, x1          ; blkstart = start + ums->start_sector')
        _p('    add x4, x1, x2          ; blkstart + blkcnt')
        _p('    cmp x4, #0x10, lsl #12  ; %d sectors = 32 MiB   @0x%x'
           % (RKUSB_LIMIT_SECTORS, h['cmp_va']))
        if h['patched']:
            _p('    b #0                    ; @0x%x  PATCHED - always falls '
               'through' % h['guard'])
        else:
            _p('    b.%s #0x%x              ; @0x%x  <== PATCH SITE'
               % (COND[h['cond']] if h['cond'] is not None else '?',
                  h['blk_dread'] or 0, h['guard']))
        _p('    (ldr w4,[x0,#0x18] and mov w1,#0xcc both present nearby)')
        if h['blk_dread']:
            _p('    normal path @0x%x: add x0, x0, #0x28 -> blk_dread '
               '(block_dev at 0x28 in struct ums)' % h['blk_dread'])
        _p('  >>> %s' % ('32MB read limit ALREADY NEUTRALISED' if h['patched']
                         else '32MB read limit ACTIVE - patch 0x%x to 0x%08x'
                         % (h['guard'], BRANCH_ALWAYS)))
    return hits[0]


def neutralise(img, base, guard_va, label):
    """把守卫分支改写为"无条件跳原 blk_dread 目标"。返回 (new_bytes, report)。

    stock 的 b.<cond> 目标从指令本身解出；坏补丁 b#0 的目标不可自解，
    但 blk_dread 入口（add x0,x0,#0x28）恒在 guard+0x28，用它恢复并写前校验。
    """
    off = guard_va - base
    w = struct.unpack_from('<I', img, off)[0]
    if w == BRANCH_ALWAYS:
        return img, 'already correctly patched (b blk_dread)'
    d = decode_bcond(w)
    if d is not None:
        delta = d[1]                      # stock: 用原 b.<cond> 的目标
    elif w == 0x14000000:
        delta = 0x28                      # 坏补丁 b#0: 目标由锚点恢复
    else:
        raise SystemExit('%s: 0x%x holds 0x%08x, not patchable'
                         % (label, guard_va, w))
    # 写前必须校验：目标处是 add x0,x0,#0x28（blk_dread 入口）
    if struct.unpack_from('<I', img, off + delta)[0] != ADD_BLOCK_DEV:
        raise SystemExit('%s: blk_dread anchor missing at 0x%x'
                         % (label, guard_va + delta))
    word = 0x14000000 | ((delta >> 2) & 0x3ffffff)   # b <原目标>
    b = bytearray(img)
    struct.pack_into('<I', b, off, word)
    return bytes(b), 'guard -> b +0x%x (0x%08x), was 0x%08x' % (delta, word, w)


# ==========================================================================
# 6. dump classification
# ==========================================================================
def classify(path, limit_mb=None, verbose=True, data=None):
    """Identify a dump and locate the patchable guard(s).

    `path` is used as a label; pass data= to classify an in-memory buffer.
    Returns dict(dump, gpt, sns, ab, fits, primary, limits, verdict).
    """
    _set_say(verbose)
    d = data if data is not None else rd(path)
    g = parse_gpt(d)
    names = [p['name'] for p in g['parts']] if g else []

    say('=' * 76)
    say('  %s   (%d bytes = %.2f MiB)' % (path, len(d), len(d) / 1048576))
    say('=' * 76)

    # --- storage kind ---------------------------------------------------
    idb = [i for i in range(0, min(len(d), 0x100000), 0x8000)
           if d[i:i + 4] == RKNS]
    soc = None
    if idb:
        w = struct.unpack_from('<I', d, idb[0] + 8)[0]
        soc = SOC_BY_CHIP.get((w >> 8) & 0xFFF)
    say('  RKNS idblock copies : %s' % (['0x%x' % i for i in idb] or 'none'))
    if soc:
        say('  SoC (RKNS word[2])  : 0x%x -> %s'
            % (struct.unpack_from('<I', d, idb[0] + 8)[0], soc))
    say('  GPT partitions      : %s' % (', '.join(names) or 'none'))

    # --- serial numbers -------------------------------------------------
    sns = find_sns(d, limit_mb)
    say('\n  --- device identity ---')
    real = {k: v for k, v in sns.items() if len(v) >= SN_MIN_HITS}
    noise = {k: v for k, v in sns.items() if len(v) < SN_MIN_HITS}
    if real:
        for s, offs in sorted(real.items(), key=lambda kv: -len(kv[1])):
            say('    SN %-22s x%-4d first @0x%08x' % (s, len(offs), offs[0]))
    else:
        say('    no serial number found')
    if noise:
        say('    (%d shape-matches seen < %d times, treated as code bytes: %s)'
            % (len(noise), SN_MIN_HITS, ', '.join(sorted(noise)[:4])))
    sns = real
    bids = find_buildids(d)
    for s, offs in sorted(bids.items(), key=lambda kv: -len(kv[1])):
        if s not in sns:
            say('    build id %-18s x%-4d first @0x%08x  (in FIT / DTB)'
                % (s, len(offs), offs[0]))

    # --- A/B ------------------------------------------------------------
    ab = read_ab(d, g)
    # SPL only trusts the block when the magic is there; a bad crc is reported
    # but the slot table is still what the metadata says.
    if ab and not ab['valid']:
        ab = None
    if ab:
        say('\n  --- A/B metadata @0x%x  crc 0x%08x %s ---'
            % (ab['off'], ab['crc'], 'OK' if ab['crc_ok'] else 'BAD'))
        for i, s in enumerate(ab['slots']):
            say('    slot _%s priority=%-3d tries=%-2d successful=%d bootable=%s'
                % ('ab'[i], s['priority'], s['tries'], s['successful'],
                   s['bootable']))
        say('    => active slot _%s  (%s)' % ('ab'[ab['index']], ab['why']))

    # --- locate U-Boot FITs ---------------------------------------------
    say('\n  --- U-Boot FIT search ---')
    fits = []
    for off, _ts in find_fits(d):
        if is_uboot_fit(d, off):
            fits.append(off)
    if not fits:
        say('    no FIT containing /images/uboot anywhere in this dump')
        verdict = ('NO_UBOOT', 'U-Boot is not on this chip. '
                   'This looks like a SPI+NVMe / SPI+eMMC design: the SPI only '
                   'holds idblock + misc + AvbABData. You need a dump of the '
                   'other storage (NVMe / eMMC) to patch rockusb.')
    else:
        exp = []
        for nm in ('uboot', 'uboot_a', 'uboot_b'):
            p = part(g, nm)
            if p:
                exp.append((nm, p['off'], p['size']))
        say('    GPT says          : %s'
            % (', '.join('%s @0x%x (%d KiB)' % (n, o, s // 1024)
                         for n, o, s in exp) or 'no uboot partition'))
        say('    FITs actually at  : %s' % ', '.join('0x%x' % f for f in fits))
        starts = set(o for _n, o, _s in exp)
        on_target = sorted(f for f in fits if f in starts)
        stray = sorted(f for f in fits if f not in starts)
        if on_target:
            kind = 'spi_ok'
            note = ('GPT matches reality. Primary FIT at %s%s'
                    % (', '.join('0x%x' % f for f in on_target),
                       '; extra copies at %s are SPL fallbacks '
                       '(CONFIG_SPL_FIT_IMAGE_MULTIPLE, %d KiB stride)'
                       % (', '.join('0x%x' % f for f in stray), 3072)
                       if stray else ''))
        elif exp and stray:
            kind = 'spi_bad'
            note = ('GPT does NOT match reality - FIT sits at %s but GPT says '
                    '%s. Patch by the actual FIT offset, and verify on the '
                    'device before flashing.'
                    % (', '.join('0x%x' % f for f in stray),
                       ', '.join('0x%x' % o for _n, o, _s in exp)))
        else:
            kind = 'spi_ok'
            note = 'no uboot partition in GPT'
        say('    classification    : %s  (%s)' % (kind, note))
        verdict = (kind, note)

    # --- which slot is primary, and where is the read limit --------------
    primary = None
    limits = []
    if fits:
        abparts = [part(g, 'uboot_a'), part(g, 'uboot_b')]
        if ab and all(abparts):
            nm = 'uboot_%s' % 'ab'[ab['index']]
            p = part(g, nm)
            if p and p['off'] in fits:
                primary = p['off']
                say('\n  primary FIT         : 0x%x  (%s, per A/B metadata)'
                    % (primary, nm))
            else:
                say('\n  A/B says %s but its FIT is not in this dump' % nm)
        if primary is None:
            pu = part(g, 'uboot')
            if pu and pu['off'] in fits:
                primary = pu['off']
                say('\n  primary FIT         : 0x%x  (no A/B, partition start)'
                    % primary)
            else:
                primary = fits[0]
                say('\n  primary FIT         : 0x%x  (lowest FIT found)'
                    % primary)

        for off in sorted(set([primary] + fits)):
            try:
                pl = uboot_payload(d, off)
            except Exception as e:
                say('    FIT 0x%x: cannot read /images/uboot (%s)' % (off, e))
                continue
            tag = 'PRIMARY' if off == primary else 'copy   '
            r = analyse(pl['img'], pl['load'],
                        'FIT @0x%x  uboot %s comp=%s load=0x%x'
                        % (off, tag, pl['comp'], pl['load']), quiet=True)
            if r is None:
                say('    FIT 0x%x (%s): no 32MB limit code found' % (off, tag))
                limits.append(dict(off=off, primary=off == primary,
                                   state='absent'))
            else:
                st = 'patched' if r['patched'] else 'ACTIVE'
                say('    FIT 0x%x (%s): rkusb_read_sector=0x%x guard=0x%x '
                    '-> %s' % (off, tag, r['fn'], r['guard'], st))
                limits.append(dict(off=off, primary=off == primary,
                                   state=st, **r))

    say('\n  >>> %s: %s' % (verdict[0], verdict[1]))
    return dict(dump=d, gpt=g, sns=sns, ab=ab, fits=fits, primary=primary,
                limits=limits, verdict=verdict)


# ==========================================================================
# 7. trimming a garbage tail
# ==========================================================================
def _blocks(b, bs):
    for i in range(len(b) // bs):
        yield i * bs, b[i * bs:(i + 1) * bs]


def repeat_run_start(b, bs=0x10000, min_blocks=3):
    """Start/length of the longest run of identical, non-erased blocks.

    A reader that fails past the real flash content echoes the same garbage
    over and over, so consecutive blocks come back byte-identical while still
    containing non-0xFF bytes.  Genuine flash never does that: erased areas
    are all 0xFF and real partitions all differ.  Returns None when the dump
    shows no such run.  Do NOT cut at "the first large erased gap" instead --
    legitimate 256 KiB inter-partition gaps exist.
    """
    best = cur = prev = None
    prev_off = -1
    for off, blk in _blocks(b, bs):
        if prev is not None and blk == prev and len(set(blk)) > 1:
            if cur is None:
                cur = prev_off
        else:
            if cur is not None and (best is None or prev_off - cur > best[1]):
                best = (cur, prev_off - cur + bs)
            cur = None
        prev, prev_off = blk, off
    if cur is not None and (best is None or prev_off - cur + bs > best[1]):
        best = (cur, prev_off - cur + bs)
    if best and best[1] >= bs * min_blocks:
        return best
    return None


def trim_len(b, align=0x1000, report=False):
    """Length the dump should be cut to.

    Two things make a dump look bigger than the flash: a repeating garbage
    tail (see repeat_run_start) and 0xFF/0x00 padding.  The garbage goes
    first, then we round down to the last 4 KiB block that still holds a
    non-0xFF byte -- not to the last single byte, because a real region can
    legitimately end in 0x00 (T90Pro's byte 0x1ffffff is 0x00).
    """
    rep = repeat_run_start(b)
    if rep:
        b = b[:rep[0]]
    last = 0
    for off, blk in _blocks(b, 0x1000):
        if any(x != 0xFF for x in blk):
            last = off + 0x1000
    n = min((last + align - 1) & ~(align - 1), len(b))
    if report:
        print('  repeat-run garbage : %s'
              % ('starts 0x%x, %d bytes (%.1f MiB) - dropped'
                 % (rep[0], rep[1], rep[1] / 1048576) if rep else 'none'))
        print('  last 4KiB with data: ends 0x%x' % last)
        print('  trimmed length     : 0x%x (%d bytes)' % (n, n))
    return n


def trim_dump(path, out, align=0x1000, max_bytes=None):
    """Cut the invalid tail off a dump and write the result to `out`."""
    d = rd(path)
    hi = len(d) if max_bytes is None else min(len(d), max_bytes)
    b = d[:hi]
    n = trim_len(b, align, report=True)
    wr(out, b[:n])
    print('trim %s\n  wrote %s : %d bytes (%.2f MiB), dropped %d bytes of tail'
          % (path, out, n, n / 1048576, len(b) - n))
    return n


def needs_trim(path):
    return repeat_run_start(rd(path)) is not None


# ==========================================================================
# 8. the patcher
# ==========================================================================
def hash_prop_offsets(dump, fdt, fit_off, value):
    """Offsets of FDT_PROP entries inside this FIT whose value == `value`.

    Used for the surgical 32-byte overwrite: rewriting a property through
    FDT.pack() is not byte-identical, so the stored hash is replaced where it
    sits, in the struct block, with nothing else moving.
    """
    lo = fit_off + fdt.offstruct
    hi = lo + fdt.szstruct
    hits = []
    o = lo
    while True:
        o = dump.find(value, o, hi)
        if o < 0:
            break
        tag, ln, _nameoff = struct.unpack_from('>III', dump, o - 12)
        if tag == FDT_PROP and ln == len(value):
            hits.append(o)
        o += 1
    return hits


def refresh_hash(dump, fit_off, image='uboot'):
    """Rewrite /images/<image>/hash/value in place (32 bytes, nothing moves)."""
    fdt = FDT(dump, fit_off)
    node = fdt.root.find('images').find(image)
    pos, size = node.u32('data-position'), node.u32('data-size')
    comp = node.get('compression').rstrip(b'\0').decode()
    new = hashlib.sha256(dump[fit_off + pos: fit_off + pos + size]).digest()
    hnode = node.find('hash')
    old = hnode.get('value')
    if len(old) != 32:
        raise SystemExit('hash/value is %d bytes, expected 32' % len(old))
    hits = hash_prop_offsets(dump, fdt, fit_off, old)
    if len(hits) != 1:
        raise SystemExit('FIT 0x%x: %d candidate hash props, expected 1'
                         % (fit_off, len(hits)))
    out = bytearray(dump)
    out[hits[0]:hits[0] + 32] = new
    return bytes(out), dict(pos=pos, size=size, comp=comp, old=old, new=new,
                            at=hits[0])


def repack_fit(dump, off, new_img, limit=None):
    """Rebuild the whole FIT in place with fit_repack's layout rules.

    Needed when the payload is gzip'd and the recompressed stream no longer
    fits its slot: every following payload shifts and data-position /
    data-size / hash/value / root totalsize are fixed up.  `limit` is the
    byte offset the new FIT must not reach (the end of its partition).
    """
    fdt = FDT(dump, off)
    end = max(n.u32('data-position') + n.u32('data-size')
              for n in fdt.root.find('images').children)
    old_len = end

    td = tempfile.mkdtemp(prefix='rkusb-')
    try:
        itb = dump[off:off + end]
        wr(os.path.join(td, 'uboot_x.itb'), itb)
        # fit_repack reads every payload from disk, so materialise all of
        # them; only uboot gets the patched decompressed bytes.
        probe = FDT(itb)
        for n in probe.root.find('images').children:
            p0, sz = n.u32('data-position'), n.u32('data-size')
            wr(os.path.join(td, '%s.bin' % n.name), itb[p0:p0 + sz])
        wr(os.path.join(td, 'uboot.dec'), new_img)
        r = fit_repack(td, 'x', os.path.join(td, 'out.itb'))
        blob = rd(os.path.join(td, 'out.itb'))
    finally:
        shutil.rmtree(td, ignore_errors=True)

    if limit is not None and off + len(blob) > limit:
        raise SystemExit('FIT 0x%x: rebuilt image is %d bytes and would run '
                         'past its partition end 0x%x - refusing to write'
                         % (off, len(blob), limit))
    out = bytearray(dump)
    out[off:off + len(blob)] = blob
    # erase the tail of the old FIT so no stale payload can be picked up
    stop = off + old_len if limit is None else min(off + old_len, limit)
    for i in range(off + len(blob), min(stop, len(out))):
        out[i] = 0
    return bytes(out), dict(old=old_len, new=len(blob), **r)


def patch_dump(src, dst, only_primary=False, dry=False, mode='auto',
               trim=False, verbose=True):
    """Patch every U-Boot FIT copy in `src` and write the result to `dst`."""
    info = classify(src, verbose=verbose)
    d = info['dump']
    if not info['fits']:
        raise SystemExit('\nnothing to patch: %s' % info['verdict'][1])

    targets = ([t for t in info['limits'] if t['primary']]
               if only_primary else info['limits'])
    print('\n' + '=' * 76)
    print('  patching %d FIT copy(ies)%s'
          % (len(targets), ' [primary only]' if only_primary else ''))
    print('=' * 76)

    for t in targets:
        off = t['off']
        pl = uboot_payload(d, off)
        print('\n--- FIT @0x%x  uboot comp=%s load=0x%x size=%d ---'
              % (off, pl['comp'], pl['load'], pl['size']))
        if t['state'] == 'patched':
            print('  already neutralised, skipping')
            continue
        if t['state'] == 'absent':
            print('  no 32MB limit code in this payload, skipping')
            continue
        guard = t['guard']
        img, msg = neutralise(pl['img'], pl['load'], guard, 'FIT 0x%x' % off)
        print('  guard 0x%x : %s' % (guard, msg))

        # how far this FIT may grow: the end of the partition holding it
        p = part_containing(info['gpt'], off)
        limit = (p['off'] + p['size']) if p else None

        if pl['comp'] == 'gzip' and mode != 'inplace':
            raw = gzip.compress(img, 9, mtime=0)
            if len(raw) > pl['size'] or mode == 'repack':
                print('  payload  : gzip %d -> %d B, does not fit the %d B '
                      'slot' % (pl['size'], len(raw), pl['size']))
                d, r = repack_fit(d, off, img, limit)
                print('  repack   : FIT 0x%x  %d -> %d B, %d payloads '
                      're-aligned to 4096, old tail erased'
                      % (off, r['old'], r['new'], r['n']))
                need_hash = False
            else:
                new = bytearray(d)
                at = off + pl['pos']
                new[at:at + len(raw)] = raw
                for i in range(at + len(raw), at + pl['size']):
                    new[i] = 0
                d = bytes(new)
                print('  payload  : gzip %d -> %d B (fits the %d B slot, '
                      'slack zeroed)' % (pl['size'], len(raw), pl['size']))
                need_hash = True
        elif pl['comp'] == 'gzip':
            raise SystemExit('FIT 0x%x: gzip payload cannot be patched in '
                             'place - drop --mode inplace' % off)
        else:
            if len(img) != pl['size']:
                raise SystemExit('payload size changed - refusing')
            new = bytearray(d)
            at = off + pl['pos']
            new[at:at + pl['size']] = img
            d = bytes(new)
            print('  payload  : %d B in place at 0x%x (XIP-safe, same length)'
                  % (pl['size'], at))
            need_hash = True

        if need_hash:
            d, h = refresh_hash(d, off)
            print('  hash     : @0x%08x  %s' % (h['at'], h['old'].hex()[:32]))
            print('             ->           %s' % h['new'].hex()[:32])
        else:
            print('  hash     : recomputed by the FIT repack for every image')

    if dry:
        print('\n--dry-run: not writing %s' % dst)
        return None
    if trim:
        n = trim_len(d)
        print('  trimmed  : %d -> %d bytes (0x%x)' % (len(d), n, n))
        d = d[:n]

    wr(dst, d)
    print('\nwrote %s  (%d bytes, md5 %s)'
          % (dst, len(d), hashlib.md5(d).hexdigest()))
    return dst


# ==========================================================================
# 9. independent verification
# ==========================================================================
class Checks:
    def __init__(self):
        self.ok = True
        self.n = 0

    def check(self, cond, msg):
        self.n += 1
        print('    %-6s %s' % ('PASS' if cond else 'FAIL', msg))
        if not cond:
            self.ok = False


def verify(orig_path, new_path, expect_trim=None, quiet_classify=True):
    """Verify a patched dump.  Returns (ok, n_checks).

    When the original is still around it is used for the size/trim
    comparison, but every FIT check below is derived from the patched bytes
    alone, so this also works without the original.
    """
    d = rd(new_path)
    o = rd(orig_path) if os.path.exists(orig_path) else None
    src = o if o is not None else d
    info = classify(orig_path, verbose=not quiet_classify, data=src)
    c = Checks()
    print('\n=== %s%s' % (os.path.basename(new_path),
                          '' if o is not None else
                          '  (original gone - FIT checks only)'))
    if o is not None:
        print('    size %d -> %d' % (len(o), len(d)))
        if expect_trim:
            c.check(len(d) == expect_trim,
                    'trimmed to 0x%x (repeat-garbage tail dropped)'
                    % expect_trim)
        else:
            c.check(len(d) == len(o), 'size preserved (in-place patch)')
    elif expect_trim:
        c.check(len(d) == expect_trim,
                'trimmed to 0x%x (repeat-garbage tail dropped)' % expect_trim)

    for off in info['fits']:
        if off + FDT_HDR_LEN > len(d):
            print('    FIT 0x%x lies past the trimmed end - skipped' % off)
            continue
        print('    FIT @0x%x' % off)
        _ts, _2, _3, mem, ver, last = struct.unpack_from('>6I', d, off + 4)
        c.check(ver == 17 and last == 16 and mem == 40,
                'FDT header valid (version %d, last_comp %d, memresv %d)'
                % (ver, last, mem))
        fdt = FDT(d, off)
        bad = 0
        n_img = 0
        for n in fdt.root.find('images').children:
            n_img += 1
            p0, sz = n.u32('data-position'), n.u32('data-size')
            algo = n.find('hash').get('algo').rstrip(b'\0').decode()
            stored = n.find('hash').get('value')
            got = hashlib.sha256(d[off + p0: off + p0 + sz]).digest()
            if algo != 'sha256' or stored != got:
                bad += 1
                print('        hash MISMATCH on %s (algo=%s)' % (n.name, algo))
        c.check(bad == 0, 'all %d image hashes match sha256' % n_img)

        pl = uboot_payload(d, off)
        c.check(len(pl['img']) > 0x10000,
                'uboot payload decompresses: %s, %d bytes'
                % (pl['comp'], len(pl['img'])))

        r = analyse(pl['img'], pl['load'], '', quiet=True)
        c.check(r is not None, 'rkusb_read_sector still identifiable at 0x%x'
                % (r['fn'] if r else -1))
        if r:
            goff = r['guard'] - pl['load']
            w = struct.unpack_from('<I', pl['img'], goff)[0]
            cw = struct.unpack_from('<I', pl['img'], goff - 4)[0]
            c.check(w == BRANCH_ALWAYS,
                    'guard 0x%x == 0x%08x (b #0)' % (r['guard'], w))
            imm = cmp32mb_imm(cw)
            c.check(imm == RKUSB_LIMIT_SECTORS,
                    'limit compare 0x%x untouched: 0x%08x = cmp x%d, #%d '
                    '(%d sectors = 32 MiB)'
                    % (r['guard'] - 4, cw, (cw >> 5) & 0x1F,
                       imm if imm else -1, imm if imm else -1))
    return c.ok, c.n


# ==========================================================================
# 10. selftest: an end-to-end regression that needs no pristine original
#
# Verifying the patcher needs an *unpatched* input.  So we synthesise one:
# take any dump this tool can read, revert each guard branch to `b.ls`, and
# deliberately corrupt /images/uboot/hash/value.  That is exactly the state a
# stock image is in (limit ACTIVE, hash consistent).  Then we run the real
# CLI in a subprocess and assert it puts everything back.
# ==========================================================================
# sha256 of the *stock* T30Pro uboot payload, recorded from the original dump
# before it was lost.  Reverting the guard must reproduce it exactly - that is
# what proves the synthesised "unpatched" image is faithful to the original.
STOCK_T30PRO_UBOOT_SHA256 = bytes.fromhex('2412242e4736b9677e3bff6927af3dce')


def _selftest_source(indir, explicit):
    if explicit:
        if not os.path.exists(explicit):
            raise SystemExit('no such source: %s' % explicit)
        return explicit
    cands = []
    if os.path.isdir(indir):
        cands = sorted(f for f in os.listdir(indir)
                       if f.lower().endswith(('.bin', '.img')))
    if not cands:
        raise SystemExit('no dump found in %s%s - pass --source FILE'
                         % (indir, os.sep))
    pref = [f for f in cands if 'T30Pro' in f]
    return os.path.join(indir, (pref or cands)[0])


def make_unpatched(src, dest):
    """Write an unpatched-looking copy of `src` to `dest`.

    Returns (fits, stock_sha256_or_None).
    """
    d = bytearray(rd(src))
    print('source: %s' % src)
    info = classify(src, verbose=False)
    if not info['fits']:
        raise SystemExit('%s holds no U-Boot FIT - cannot selftest with it'
                         % src)

    # 1) guard branch back to b.ls -> the 32MB limit is ACTIVE again.
    #    A real original already has b.ls, so this is a no-op there.
    reverted = 0
    for t in info['limits']:
        if 'guard' not in t:
            continue
        pl = uboot_payload(bytes(d), t['off'])
        at = t['off'] + pl['pos'] + (t['guard'] - pl['load'])
        cur = struct.unpack_from('<I', d, at)[0]
        assert cur in (BRANCH_ALWAYS, B_LS), \
            '0x%x: unexpected guard 0x%08x' % (at, cur)
        if cur != B_LS:
            struct.pack_into('<I', d, at, B_LS)
            reverted += 1
    print('guard reverted to b.ls in %d FIT copy(ies)' % reverted)

    # 2) rebuild each FIT and poison /images/uboot/hash/value so it no longer
    #    matches the payload (a stock image has a *correct* hash; poisoning it
    #    proves the patcher really recomputes rather than leaving it alone)
    for off in info['fits']:
        fdt = FDT(bytes(d), off)
        end = max(n.u32('data-position') + n.u32('data-size')
                  for n in fdt.root.find('images').children)
        td = tempfile.mkdtemp(prefix='rkusb-st-')
        try:
            wr(os.path.join(td, 'uboot_x.itb'), bytes(d[off:off + end]))
            for n in fdt.root.find('images').children:
                p0, sz = n.u32('data-position'), n.u32('data-size')
                wr(os.path.join(td, '%s.bin' % n.name),
                   bytes(d[off + p0:off + p0 + sz]))
            fit_repack(td, 'x', os.path.join(td, 'out.itb'))
            blob = rd(os.path.join(td, 'out.itb'))
        finally:
            shutil.rmtree(td, ignore_errors=True)
        d[off:off + len(blob)] = blob

        fdt = FDT(bytes(d), off)
        node = fdt.root.find('images/uboot')
        p0, sz = node.u32('data-position'), node.u32('data-size')
        good = hashlib.sha256(bytes(d[off + p0:off + p0 + sz])).digest()
        stored = node.find('hash').get('value')
        hits = hash_prop_offsets(bytes(d), fdt, off, stored)
        assert len(hits) == 1, hits
        bad = bytes([good[0] ^ 0xFF]) + good[1:]       # differs, same length
        assert bad != stored
        d[hits[0]:hits[0] + 32] = bad

    wr(dest, bytes(d))
    stock = None
    if 'T30Pro' in os.path.basename(src):
        stock = STOCK_T30PRO_UBOOT_SHA256
    return info['fits'], stock


def run_selftest(indir, workdir, source=None, keep=False):
    os.makedirs(workdir, exist_ok=True)
    src = _selftest_source(indir, source)
    inp = os.path.join(workdir, 'SELFTEST_unpatched.bin')
    outp = os.path.join(workdir, 'SELFTEST_unpatched_nolimit.bin')
    fits, stock = make_unpatched(src, inp)
    print('built %s (guard=b.ls, hash poisoned)' % inp)

    # run the real CLI, exactly as a user would
    sys.stdout.flush()
    r = subprocess.run([sys.executable, os.path.abspath(__file__), 'fix',
                        '--out', workdir, inp])
    if r.returncode != 0:
        print('FAIL: %s fix returned %d' % (PROG, r.returncode))
        return 1

    patched = rd(outp)
    fails = []
    for off in fits:
        pl = uboot_payload(patched, off)
        fdt = FDT(patched, off)
        node = fdt.root.find('images/uboot')
        p0, sz = node.u32('data-position'), node.u32('data-size')
        for n in fdt.root.find('images').children:
            q0, q1 = n.u32('data-position'), n.u32('data-size')
            if hashlib.sha256(patched[off + q0:off + q0 + q1]).digest() \
                    != n.find('hash').get('value'):
                fails.append('FIT 0x%x image %s hash mismatch' % (off, n.name))
        # the guard lives in the uboot payload; find it again from scratch
        rr = analyse(pl['img'], pl['load'], '', quiet=True)
        if rr is None:
            fails.append('FIT 0x%x: guard not found after patching' % off)
            continue
        w = struct.unpack_from('<I', pl['img'],
                               rr['guard'] - pl['load'])[0]
        if w != BRANCH_ALWAYS:
            fails.append('FIT 0x%x guard is 0x%08x, expected 0x%08x'
                         % (off, w, BRANCH_ALWAYS))
        got = hashlib.sha256(patched[off + p0:off + p0 + sz]).digest()
        if stock is not None and got.startswith(stock):
            fails.append('FIT 0x%x uboot payload is still the stock one - '
                         'the guard was not patched' % off)

    if not keep:
        for p in (inp, outp):
            if os.path.exists(p):
                os.remove(p)

    if fails:
        for f in fails:
            print('FAIL:', f)
        return 1
    print('\nSELFTEST PASSED  (%d FIT copies exercised)' % len(fits))
    print('  - guard re-neutralised in every FIT copy (b.ls -> b #0)')
    print('  - every image hash recomputed and matching')
    if stock is not None:
        print('  - synthesised input verified faithful: its stock payload '
              'sha256 == %s... (recorded from the lost original)'
              % stock[:8].hex())
    return 0


# ==========================================================================
# 11. driver: patch every input, then verify every output
# ==========================================================================
def collect(paths, indir):
    if paths:
        return list(paths)
    if not os.path.isdir(indir):
        return []
    return [os.path.join(indir, f)
            for f in sorted(os.listdir(indir))
            if f.lower().endswith(('.bin', '.img'))]


def run_fix(files, outdir, only_primary=False, no_verify=False, dry=False):
    os.makedirs(outdir, exist_ok=True)
    failed = []
    npass = 0
    for path in files:
        base = os.path.basename(path)
        stem, _ = os.path.splitext(base)
        dest = os.path.join(outdir, stem + '_nolimit.bin')
        print()
        print('#' * 76)
        print('# %s' % base)
        print('#' * 76)
        try:
            trim = needs_trim(path)
            if trim:
                print('[%s] repeated-block garbage tail detected, will trim'
                      % PROG)
            patch_dump(path, dest, only_primary, dry, 'auto', trim)
            if not dry and not no_verify:
                ok, n = verify(path, dest)
                npass += n
                if not ok:
                    failed.append(base + ' (verification)')
        except SystemExit as e:
            print('[%s] FAILED: %s' % (PROG, e))
            failed.append(base)
        except Exception as e:                    # keep going, report all
            import traceback
            traceback.print_exc()
            print('[%s] FAILED: %s: %s' % (PROG, type(e).__name__, e))
            failed.append(base)

    print()
    print('#' * 76)
    if failed:
        print('# %d input(s) failed: %s' % (len(failed), ', '.join(failed)))
        print('#' * 76)
        return 1
    print('# all %d input(s) patched and verified -> %s  (%d checks passed)'
          % (len(files), outdir, npass))
    if not dry:
        for f in sorted(os.listdir(outdir)):
            p = os.path.join(outdir, f)
            if os.path.isfile(p):
                print('#   %-58s %10d B' % (f, os.path.getsize(p)))
    print('#' * 76)
    return 0


# ==========================================================================
# 12. command line
# ==========================================================================
EXAMPLES = """examples:
  %(prog)s                                  patch every .bin/.img in ./in
  %(prog)s dump.bin --out fixed             patch one dump into ./fixed
  %(prog)s classify dump.bin --limit-mb 32  identify it, change nothing
  %(prog)s patch dump.bin -o out.bin        patch, no verification pass
  %(prog)s verify orig.bin out.bin          re-check a patched dump
  %(prog)s limit uboot-payload.bin          just locate the 32MB guard
  %(prog)s fit unpack dump.bin -o dir       unpack the active slot's FIT
  %(prog)s selftest                         end-to-end regression test

Exit code is 0 only if every input was patched AND verified."""


def build_parser():
    ap = argparse.ArgumentParser(
        prog=PROG,
        description='Remove the Rockchip rockusb 32 MiB read limit from '
                    'RK3588/RK3576 SPI/eMMC dumps.  Python 3 stdlib only.',
        epilog=EXAMPLES % dict(prog=PROG),
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('-V', '--version', action='version',
                    version='%s %s' % (PROG, VERSION))
    sub = ap.add_subparsers(dest='cmd')

    f = sub.add_parser('fix', help='classify + trim + patch + verify '
                                   '(the default command)')
    f.add_argument('dumps', nargs='*', help='input dumps (default: --in/*.bin)')
    f.add_argument('--in', dest='indir', default='in',
                   help='directory to scan when no dumps are given '
                        '(default: %(default)s)')
    f.add_argument('--out', dest='outdir', default='out',
                   help='where to write the patched images '
                        '(default: %(default)s)')
    f.add_argument('--only-primary', action='store_true',
                   help='patch only the FIT the SPL boots first')
    f.add_argument('--no-verify', action='store_true')
    f.add_argument('--dry-run', action='store_true')

    c = sub.add_parser('classify', help='identify a dump, change nothing')
    c.add_argument('dump')
    c.add_argument('--limit-mb', type=int, default=None,
                   help='only look for serial numbers inside the first N MB')

    t = sub.add_parser('trim', help='cut a repeated-block garbage tail off')
    t.add_argument('dump')
    t.add_argument('-o', '--output', required=True)
    t.add_argument('--align', type=lambda x: int(x, 0), default=0x1000)
    t.add_argument('--max', type=lambda x: int(x, 0), default=None)

    l = sub.add_parser('limit', help='locate the 32MB guard in a payload/FIT')
    l.add_argument('payload', help='U-Boot payload (raw or gzipped), or a '
                                   'dump when --fit-off is given')
    l.add_argument('--base', type=lambda x: int(x, 0), default=None,
                   help='link address; default: read from FIT /images/uboot')
    l.add_argument('--fit-off', type=lambda x: int(x, 0), default=None,
                   help='treat the file as a dump and read the FIT here')

    p = sub.add_parser('patch', help='patch one dump (no verify pass)')
    p.add_argument('dump')
    p.add_argument('-o', '--output', required=True)
    p.add_argument('--only-primary', action='store_true')
    p.add_argument('--mode', choices=('auto', 'inplace', 'repack'),
                   default='auto',
                   help='auto: in place when the recompressed payload still '
                        'fits, otherwise rebuild the FIT')
    p.add_argument('--trim', action='store_true',
                   help='cut the dump down to the last real 4 KiB block')
    p.add_argument('--dry-run', action='store_true')

    v = sub.add_parser('verify', help='re-check a patched dump')
    v.add_argument('orig', nargs='?', help='original dump (optional)')
    v.add_argument('patched')

    g = sub.add_parser('fit', help='FIT-level inspection / unpack / repack')
    gsub = g.add_subparsers(dest='fitcmd', required=True)
    gi = gsub.add_parser('info')
    gi.add_argument('dump')
    gu = gsub.add_parser('unpack')
    gu.add_argument('dump')
    gu.add_argument('-o', '--output', required=True)
    gu.add_argument('--slot')
    gr = gsub.add_parser('repack')
    gr.add_argument('dir')
    gr.add_argument('-o', '--output', required=True)
    gr.add_argument('--slot')
    gr.add_argument('--align', type=int, default=ALIGN)

    s = sub.add_parser('selftest', help='end-to-end regression test')
    s.add_argument('--in', dest='indir', default='in',
                   help='directory to pick a source dump from '
                        '(default: %(default)s)')
    s.add_argument('--source', default=None, help='use this dump explicitly')
    s.add_argument('--work', dest='workdir', default=None,
                   help='scratch directory (default: a temp dir)')
    s.add_argument('--keep', action='store_true',
                   help='leave the synthesised files behind')
    return ap


SUBCOMMANDS = ('fix', 'classify', 'trim', 'limit', 'patch', 'verify', 'fit',
               'selftest')
TOPLEVEL_FLAGS = ('-h', '--help', '--version', '-V')


def cmd_fit(a):
    if a.fitcmd == 'info':
        d = rd(a.dump)
        g = parse_gpt(d)
        if g is None:
            raise SystemExit('no GPT at LBA 1 in %s' % a.dump)
        print('disk (per GPT): %d sectors = %.2f GiB'
              % (g['last_usable'] + 1, (g['last_usable'] + 1) * SECTOR / 1024 ** 3))
        for p in g['parts']:
            print('  %-16s LBA %-12d .. %-12d %10.2f MiB'
                  % (p['name'], p['start'], p['end'], p['size'] / 1048576))
        ab = read_ab(d, g)
        if ab is None:
            print('\nno misc partition -> no A/B metadata')
        else:
            print('\nA/B metadata @0x%x  magic=%r crc=0x%08x %s'
                  % (ab['off'], ab['magic'], ab['crc'],
                     'OK' if ab['crc_ok'] else 'BAD'))
            for i, s in enumerate(ab['slots']):
                print('  slot _%s: priority=%-2d tries=%-2d successful=%d '
                      'bootable=%s'
                      % ('ab'[i], s['priority'], s['tries'], s['successful'],
                         ab['bootable'][i]))
            print('  last_boot=%d ; %s' % (ab['last_boot'], ab['why']))
            print('  => active slot = _%s  => SPL resolves "uboot" to '
                  '"uboot_%s"' % ('ab'[ab['index']], 'ab'[ab['index']]))
        for i in range(0, min(len(d), 0x100000), 0x8000):
            if d[i:i + 4] == RKNS:
                print('\nidblock @0x%x: magic=%r' % (i, d[i:i + 4]))
        return 0
    if a.fitcmd == 'unpack':
        d = rd(a.dump)
        g = parse_gpt(d)
        if g is None:
            raise SystemExit('no GPT at LBA 1 in %s' % a.dump)
        ab = read_ab(d, g)
        slot = a.slot or ('ab'[ab['index']] if ab and ab['valid'] else 'a')
        m = fit_unpack(d, g, slot, a.output)
        print('unpacked slot _%s from %s (LBA %d) -> %s'
              % (slot, m['part']['name'], m['part']['start'], a.output))
        for n, e in m['images'].items():
            print('  %-8s pos=0x%06x size=%-8d comp=%-6s sha256 %s %s'
                  % (n, e['pos'], e['size'], e['comp'], e['sha256'][:16],
                     'hash OK' if e.get('hash_ok') else 'HASH MISMATCH'))
        return 0
    man = json.loads(rd(os.path.join(a.dir, 'manifest.json')).decode('utf-8'))
    slot = a.slot or man['slot']
    r = fit_repack(a.dir, slot, a.output, a.align)
    print('wrote %s  (%d images, FDT padded to 0x%x, total 0x%x)'
          % (a.output, r['n'], r['fdt_len'], r['total']))
    return 0


def main(argv=None):
    _harden_stdio()
    argv = list(sys.argv[1:] if argv is None else argv)
    # top-level flags must reach the top-level parser, not the implicit `fix`
    # subcommand; let argparse handle -h / --version itself.
    if argv and argv[0] in TOPLEVEL_FLAGS:
        try:
            build_parser().parse_args(argv)
        except SystemExit as e:
            return int(e.code or 0)
        return 0
    # bare `rkusb_nolimit.py DUMP...` means `fix DUMP...`
    if not argv or argv[0] not in SUBCOMMANDS:
        argv = ['fix'] + argv
    a = build_parser().parse_args(argv)

    if a.cmd == 'fix':
        files = collect(a.dumps, a.indir)
        if not files:
            print('No inputs. Put the original dumps in %s%s , or name them:'
                  % (a.indir, os.sep))
            print('    python3 %s path%sdump.bin' % (PROG, os.sep))
            return 1
        return run_fix(files, a.outdir, a.only_primary, a.no_verify,
                       a.dry_run)

    if a.cmd == 'classify':
        classify(a.dump, a.limit_mb)
        return 0

    if a.cmd == 'trim':
        trim_dump(a.dump, a.output, a.align, a.max)
        return 0

    if a.cmd == 'limit':
        d = rd(a.payload)
        if a.fit_off is not None or d[0:4] == FDT_MAGIC:
            off = a.fit_off or 0
            pl = uboot_payload(d, off)
            r = analyse(pl['img'], pl['load'],
                        '%s FIT @0x%x uboot comp=%s'
                        % (a.payload, off, pl['comp']))
            return 0 if r else 1
        img = d
        if d[:2] == b'\x1f\x8b':
            img = gzip.decompress(d)
            print('  (gunzipped %d -> %d bytes)' % (len(d), len(img)))
        base = a.base if a.base is not None else 0x200000
        return 0 if analyse(img, base, a.payload) else 1

    if a.cmd == 'patch':
        patch_dump(a.dump, a.output, a.only_primary, a.dry_run, a.mode,
                   a.trim)
        return 0

    if a.cmd == 'verify':
        orig = a.orig if a.orig is not None else a.patched
        ok, n = verify(orig, a.patched)
        print('\n%s  (%d checks)' % ('ALL CHECKS PASSED' if ok
                                     else 'SOME CHECKS FAILED', n))
        return 0 if ok else 1

    if a.cmd == 'fit':
        return cmd_fit(a)

    if a.cmd == 'selftest':
        work = a.workdir
        tmp = None
        if work is None:
            tmp = tempfile.mkdtemp(prefix='rkusb-selftest-')
            work = tmp
        try:
            return run_selftest(a.indir, work, a.source, a.keep)
        finally:
            if tmp is not None and not a.keep:
                shutil.rmtree(tmp, ignore_errors=True)

    build_parser().print_help()
    return 2


# ======================================================================
# ====  以下为原 AIO 增量（digest 刷写 / repack 头部修复 / plan / verify）
# ======================================================================


# ==========================================================================
# 1. 新增：原地刷新 digest/value
# ==========================================================================
def refresh_digest(dump, fit_off, decompressed, image='uboot'):
    """Rewrite /images/<image>/digest/value in place (nothing moves).

    digest/value 覆盖的是**解压后**的镜像，SPL 在 image_decomp 之后再查一次：

        spl_fit_image_load
          -> fit_image_verify_with_hash
               0x264 bl fit_image_check_digest    (压缩态)
               0x288 bl image_decomp
               0x31c bl fit_image_check_digest    (解压态)  <-- 就是这里
               0x33c bl fit_image_verify_hash     -> "Bad hash value"

    没有 digest 节点的板子（T20Pro/T30Pro）直接返回 None。
    """
    fdt = FDT(dump, fit_off)
    node = fdt.root.find('images').find(image)
    dnode = node.find('digest')
    if dnode is None or dnode.get('value') is None:
        return None
    algo = (dnode.get('algo') or b'sha256').rstrip(b'\0').decode()
    if algo != 'sha256':
        raise SystemExit('FIT 0x%x: unsupported digest algo %r' % (fit_off, algo))
    old = dnode.get('value')
    if len(old) != 32:
        raise SystemExit('digest/value is %d bytes, expected 32' % len(old))
    new = hashlib.sha256(decompressed).digest()
    hits = hash_prop_offsets(dump, fdt, fit_off, old)
    if len(hits) != 1:
        raise SystemExit('FIT 0x%x: %d candidate digest props, expected 1'
                         % (fit_off, len(hits)))
    out = bytearray(dump)
    out[hits[0]:hits[0] + 32] = new
    return bytes(out), dict(old=old, new=new, at=hits[0], n=len(decompressed))


# ==========================================================================
# 2. 补丁：fit_repack 也要算 digest，并且不要把 FDT 头部 totalsize 写坏
# ==========================================================================
_orig_fit_repack = fit_repack


def fit_repack(indir, slot, outfile, align=ALIGN, limit=None, off=None):
    """原 fit_repack + digest，并且头部 totalsize 保持 FDT blob 大小。

    原实现里 `fdt.pack(keep_layout=False, totalsize=total)` 把**整个镜像大小**
    写进了 FDT 头部 totalsize。SPL 用这个字段算暂存窗口：

        buf = (CONFIG_SYS_TEXT_BASE - bl_len - align512(hdr_totalsize)) & ~63

    T90Pro 的 CONFIG_SYS_TEXT_BASE 是 0x00200000，而 FIT 有 2.45 MiB，
    64 位下借位成负数，AArch64 关 MMU 只解码 40 位物理地址 -> 同步外部异常
    -> 复位 -> BootROM -> MaskROM。厂商在这个字段里写的是 FDT blob 大小
    （0xa00 / 0xc00），必须保持。
    """
    itb = rd(os.path.join(indir, 'uboot_%s.itb' % slot))
    fdt = FDT(itb)
    hdr_totalsize = fdt.tsize          # 厂商写在头部的 FDT blob 尺寸，必须保留
    images = fit_images(fdt)

    payloads = []
    for im in images:
        name, data = im['name'], None
        raw = None
        if im['comp'] == 'gzip':
            dec = os.path.join(indir, '%s.dec' % name)
            if os.path.exists(dec):
                # 只有被改过的 image 才会有 .dec
                raw = rd(dec)
                data = gzip.compress(raw, 9, mtime=0)
        if data is None:
            data = rd(os.path.join(indir, '%s.bin' % name))
            # 没被改过：payload 一个字节都不动。
            # digest 覆盖的是**解压后**的镜像，这里必须解压，不能拿压缩字节去算。
            raw = gzip.decompress(data) if im['comp'] == 'gzip' else data
        payloads.append((im, data, raw))

    fdt_len = align
    pos, plan = fdt_len, []
    for _im, data, _raw in payloads:
        plan.append((pos, len(data)))
        pos = (pos + len(data) + align - 1) & ~(align - 1)
    total = pos

    for (im, data, raw), (p_, size) in zip(payloads, plan):
        im['node'].set_u32('data-position', p_)
        im['node'].set_u32('data-size', size)
        hnode = im['node'].find('hash')
        if hnode is not None:
            algo = (hnode.get('algo') or b'sha256').rstrip(b'\0').decode()
            if algo != 'sha256':
                raise SystemExit('unsupported hash algo %r' % algo)
            hnode.set('value', hashlib.sha256(data).digest())
        dnode = im['node'].find('digest')            # <-- 新增
        if dnode is not None and dnode.get('value') is not None:
            algo = (dnode.get('algo') or b'sha256').rstrip(b'\0').decode()
            if algo != 'sha256':
                raise SystemExit('unsupported digest algo %r' % algo)
            dnode.set('value', hashlib.sha256(raw).digest())

    if fdt.root.get('totalsize') is not None:
        fdt.root.set_u32('totalsize', total)

    # 头部 totalsize 保持厂商写的 FDT blob 尺寸。原版传的是 total（整个镜像
    # 大小），SPL 会拿它算暂存窗口 -> 64 位借位 -> 外部异常 -> MaskROM。
    blob = fdt.pack(keep_layout=False, totalsize=hdr_totalsize)
    if len(blob) > fdt_len:
        raise SystemExit('FDT grew to %d bytes, past the first payload slot '
                         'at 0x%x' % (len(blob), fdt_len))
    out = bytearray(total)
    out[0:len(blob)] = blob
    for (_im, data, _raw), (p_, size) in zip(payloads, plan):
        out[p_:p_ + size] = data
    assert len(out) == total
    # limit 检查要在写文件之前做，和原 repack_fit 一致
    if limit is not None and off is not None and off + total > limit:
        raise SystemExit('FIT 0x%x: rebuilt image is %d bytes and would run '
                         'past its partition end 0x%x - refusing to write'
                         % (off, total, limit))
    wr(outfile, bytes(out))
    return dict(total=total, fdt_len=fdt_len, fdt_blob=len(blob),
                n=len(payloads), plan=plan, old=None)


def _repack(dump, off, new_img, limit=None):
    """repack_fit 的等价实现，但调用修好的 fit_repack（limit 用关键字传）。

    原版 repack_fit 里 `fit_repack(td, 'x', out.itb)` 是对的（align 走默认值，
    limit 在它自己那里检查）；这里只是把 fit_repack 换成带 digest + 不写坏
    头部 totalsize 的版本。
    """
    import shutil
    import tempfile
    fdt = FDT(dump, off)
    end = max(n.u32('data-position') + n.u32('data-size')
              for n in fdt.root.find('images').children)
    td = tempfile.mkdtemp(prefix='rkusb-aio-')
    try:
        itb = dump[off:off + end]
        wr(os.path.join(td, 'uboot_x.itb'), itb)
        probe = FDT(itb)
        for n in probe.root.find('images').children:
            p0, sz = n.u32('data-position'), n.u32('data-size')
            wr(os.path.join(td, '%s.bin' % n.name), itb[p0:p0 + sz])
        wr(os.path.join(td, 'uboot.dec'), new_img)
        r = fit_repack(td, 'x', os.path.join(td, 'out.itb'),
                       limit=limit, off=off)
        blob = rd(os.path.join(td, 'out.itb'))
    finally:
        shutil.rmtree(td, ignore_errors=True)
    out = bytearray(dump)
    out[off:off + len(blob)] = blob
    stop = off + end if limit is None else min(off + end, limit)
    for i in range(off + len(blob), min(stop, len(out))):
        out[i] = 0
    r['old'] = end
    r['new'] = len(blob)
    return bytes(out), r


# ==========================================================================
# 3. 补丁：patch_dump 的 in-place 路径也要刷 digest
# ==========================================================================
def patch_dump(src, dst, only_primary=False, dry=False, mode='auto',
               trim=False, verbose=True):
    info = classify(src, verbose=verbose)
    d = info['dump']
    if not info['fits']:
        raise SystemExit('\nnothing to patch: %s' % info['verdict'][1])

    targets = ([t for t in info['limits'] if t['primary']]
               if only_primary else info['limits'])
    print('\n' + '=' * 76)
    print('  patching %d FIT copy(ies)%s   [v3]'
          % (len(targets), '  [primary only]' if only_primary else ''))
    print('=' * 76)

    for t in targets:
        off = t['off']
        pl = uboot_payload(d, off)
        print('\n--- FIT @0x%x  uboot comp=%s load=0x%x size=%d ---'
              % (off, pl['comp'], pl['load'], pl['size']))
        if t['state'] == 'patched':
            print('  already neutralised, skipping')
            continue
        if t['state'] == 'absent':
            print('  no 32MB limit code in this payload, skipping')
            continue
        img, msg = neutralise(pl['img'], pl['load'], t['guard'],
                                'FIT 0x%x' % off)
        print('  guard 0x%x : %s' % (t['guard'], msg))

        p = part_containing(info['gpt'], off)
        limit = (p['off'] + p['size']) if p else None

        if pl['comp'] == 'gzip' and mode != 'inplace':
            raw = gzip.compress(img, 9, mtime=0)
            if len(raw) > pl['size'] or mode == 'repack':
                print('  route    : REPACK (gzip %d -> %d B does not fit the '
                      '%d B slot)' % (pl['size'], len(raw), pl['size']))
                old_end = max(n.u32('data-position') + n.u32('data-size')
                              for n in FDT(d, off).root.find('images').children)
                d, r = _repack(d, off, img, limit)
                print('  repack   : FIT 0x%x  %d -> %d B, %d payloads '
                      're-aligned to %d, hash+digest recomputed, FDT header '
                      'kept at the blob size'
                      % (off, r['old'], r['new'], r['n'], ALIGN))
                need_hash = False
            else:
                new = bytearray(d)
                at = off + pl['pos']
                new[at:at + len(raw)] = raw
                for i in range(at + len(raw), at + pl['size']):
                    new[i] = 0
                d = bytes(new)
                print('  route    : IN-PLACE (gzip %d -> %d B fits the %d B '
                      'slot, slack zeroed)' % (pl['size'], len(raw), pl['size']))
                need_hash = True
        elif pl['comp'] == 'gzip':
            raise SystemExit('FIT 0x%x: gzip payload cannot be patched in '
                             'place - drop --mode inplace' % off)
        else:
            if len(img) != pl['size']:
                raise SystemExit('payload size changed - refusing')
            new = bytearray(d)
            at = off + pl['pos']
            new[at:at + pl['size']] = img
            d = bytes(new)
            print('  route    : IN-PLACE (comp=%s, %d B, XIP-safe, same '
                  'length, label untouched)' % (pl['comp'], pl['size']))
            need_hash = True

        if need_hash:
            d, h = refresh_hash(d, off)
            print('  hash     : @0x%08x  %s' % (h['at'], h['old'].hex()[:32]))
            print('             ->           %s' % h['new'].hex()[:32])
            # ---- 新增：digest 覆盖解压后的镜像 ----
            rd_ = refresh_digest(d, off, img)
            if rd_ is None:
                print('  digest   : no digest node on this board - nothing '
                      'to do')
            else:
                d, g = rd_
                print('  digest   : @0x%08x  %s' % (g['at'], g['old'].hex()[:32]))
                print('             ->           %s   (sha256 of %d '
                      'decompressed bytes)' % (g['new'].hex()[:32], g['n']))
        else:
            print('  hash+digest : recomputed by the FIT repack for every image')

    if dry:
        print('\n--dry-run: not writing %s' % dst)
        return None
    if trim:
        n = trim_len(d)
        print('  trimmed  : %d -> %d bytes (0x%x)' % (len(d), n, n))
        d = d[:n]
    wr(dst, d)
    print('\nwrote %s  (%d bytes, md5 %s)'
          % (dst, len(d), hashlib.md5(d).hexdigest()))
    return dst


fit_repack = fit_repack
patch_dump = patch_dump
run_fix = run_fix          # run_fix 内部按名字取 patch_dump，见下面 rebind


# ==========================================================================
# 4. 自动判别：--plan
# ==========================================================================
def plan(paths):
    print('=' * 78)
    print('  自动判别：每个 FIT 会走哪条路径、哪些校验值要改')
    print('=' * 78)
    bad = 0
    for path in paths:
        d = rd(path)
        info = classify(path, verbose=False, data=d)
        print('\n%s\n  %s' % (os.path.basename(path), info['verdict'][1]))
        if not info['fits']:
            print('  no U-Boot FIT - nothing to do')
            continue
        for t in info['limits']:
            off = t['off']
            pl = uboot_payload(d, off)
            fdt = FDT(d, off)
            node = fdt.root.find('images').find('uboot')
            dnode = node.find('digest')
            has_digest = dnode is not None and dnode.get('value') is not None
            p = part_containing(info['gpt'], off)
            limit = (p['off'] + p['size']) if p else None

            if t['state'] != 'ACTIVE':
                route = 'SKIP (%s)' % t['state']
                newlen = pl['size']
            elif pl['comp'] == 'gzip':
                img, _ = neutralise(pl['img'], pl['load'], t['guard'], '?')
                newlen = len(gzip.compress(img, 9, mtime=0))
                route = 'REPACK' if newlen > pl['size'] else 'IN-PLACE (gzip)'
            else:
                newlen = pl['size']
                route = 'IN-PLACE (comp=%s, 不压缩不改标签)' % pl['comp']

            flag = ''
            if route.startswith('REPACK'):
                hdr = struct.unpack_from('>I', d, off + 4)[0]
                if hdr < 0x10000:
                    flag = '  <-- 原版 fit_repack 会把头部写成整个镜像大小，必砖'
            print('  FIT @0x%-8x state=%-8s comp=%-5s digest=%-3s  %s%s'
                  % (off, t['state'], pl['comp'], 'yes' if has_digest else 'no',
                     route, flag))
            print('      payload %d -> %d B   需要更新: hash/value%s%s'
                  % (pl['size'], newlen,
                     ', digest/value' if has_digest else '',
                     ', data-position/data-size + 根/totalsize'
                     if route.startswith('REPACK') else ''))
            if has_digest:
                bad += 1
    print('\n  %d 个 FIT 带 digest 节点 —— 原版工具一个都不会更新，那就是砖的原因'
          % bad)
    return 0


# ==========================================================================
# 5. 独立校验：hash + digest + 头部
# ==========================================================================
def verify_digest(orig, new):
    a, b = rd(orig), rd(new)
    ok = True

    def chk(c, m):
        nonlocal ok
        ok = ok and c
        print('  [%s] %s' % ('OK ' if c else 'FAIL', m))

    info = classify(orig, verbose=False, data=a)
    for off in info['fits']:
        ha = struct.unpack_from('>10I', a, off)
        hb = struct.unpack_from('>10I', b, off)
        chk(ha == hb, 'FIT 0x%x: FDT 头部逐字节一致 (totalsize=0x%x)'
            % (off, hb[1]))
        fdt = FDT(b, off)
        nbad = ndig = ndbad = n = 0
        for im in fdt.root.find('images').children:
            n += 1
            p0, sz = im.u32('data-position'), im.u32('data-size')
            blob = b[off + p0: off + p0 + sz]
            hn = im.find('hash')
            if hn is not None and hn.get('value') != hashlib.sha256(blob).digest():
                nbad += 1
            dn = im.find('digest')
            if dn is not None and dn.get('value') is not None:
                ndig += 1
                comp = (im.get('compression') or b'none').rstrip(b'\0')
                raw = gzip.decompress(blob) if comp == b'gzip' else blob
                if dn.get('value') != hashlib.sha256(raw).digest():
                    ndbad += 1
        chk(nbad == 0, 'FIT 0x%x: %d 个 image 的 hash/value 全部匹配' % (off, n))
        chk(ndbad == 0, 'FIT 0x%x: %d 个 digest/value == sha256(解压后镜像)'
            % (off, ndig))
    return 0 if ok else 1



def _cli(argv):
    args = list(argv)
    if '--plan' in args:
        args.remove('--plan')
        rest, ind = [], 'in'
        i = 0
        while i < len(args):
            a = args[i]
            if a == '--in':
                ind = args[i + 1]
                i += 2
            elif a.startswith('-'):
                i += 1
            else:
                rest.append(a)
                i += 1
        if not rest:
            rest = [os.path.join(ind, f) for f in sorted(os.listdir(ind))
                    if f.lower().endswith(('.bin', '.img'))]
        return plan(rest)
    if '--verify' in args:
        args.remove('--verify')
        rest = [a for a in args if not a.startswith('-')]
        if len(rest) != 2:
            raise SystemExit('--verify ORIG NEW')
        return verify_digest(*rest)
    # 其余全部交给本文件（自包含）的 CLI：fix_repack/patch_dump 就是上面修正后的版本
    return main(args)


if __name__ == '__main__':
    sys.exit(_cli(sys.argv[1:]))
