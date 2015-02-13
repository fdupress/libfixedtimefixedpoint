#!/usr/bin/env python
import sys
import math
import decimal
from decimal import Decimal

# We might overwrite base.py; make sure we don't generate bytecode...
sys.dont_write_bytecode = True

# If we've customized things, keep the customizations. Otherwise, revert to
# something reasonable...
try:
  from base import *
except:
  flag_bits = 2
  int_bits  = 31
  frac_bits = (64 - flag_bits - int_bits)

  # We're going for 48-bit accuracy on log and exp.
  # TODO: explain everything usefully in documentation
  internal_frac_bits = 50
  internal_int_bits = 14

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument('--intbits', metavar='N', type=int, nargs='?',
                     help='The number of integer bits', default = None)
    parser.add_argument('--flagbits', metavar='N', type=int, nargs='?',
                     help='The number of flag bits', default = None)
    parser.add_argument('--fracbits', metavar='N', type=int, nargs='?',
                     help='The number of fraction bits', default = None)
    parser.add_argument('--file', metavar='filename', nargs='?', type=argparse.FileType(mode="w"),
                     help='The filename to write to', default = None)
    parser.add_argument('--pyfile', metavar='filename', nargs='?', type=argparse.FileType(mode="w"),
                     help='The filename to write the python base to', default = None)
    parser.add_argument('--lutfile', metavar='filename', nargs='?', type=argparse.FileType(mode="w"),
                     help='The filename to write the C LUT file to', default = None)
    args = vars(parser.parse_args())

    if args["flagbits"] is not None:
        flag_bits = args["flagbits"]

    aint = args["intbits"]
    afrac = args["fracbits"]

    if aint is None and afrac is None:
        pass
    elif aint is None and afrac is not None:
        frac_bits = afrac
        int_bits = (64 - flag_bits - frac_bits)
    elif aint is not None and afrac is None:
        int_bits = aint
        frac_bits = (64 - flag_bits - int_bits)
    elif aint is not None and afrac is not None:
        int_bits = aint
        frac_bits = afrac

    # Check sanity
    if (flag_bits + int_bits + frac_bits) > 64:
        print "Too many bits! (%d (flag) + %d (int) + %d (frac) > 64)"%(flag_bits, int_bits, frac_bits)
        sys.exit(1)
    if (flag_bits + int_bits + frac_bits) < 64:
        print "Not enough bits! (%d (flag) + %d (int) + %d (frac) < 64)"%(flag_bits, int_bits, frac_bits)
        sys.exit(1)
    if int_bits < 1:
        print "There must be at least one integer bit (for two's complement...)"
        print "You asked for %d (flag), %d (int), and %d (frac)"%(flag_bits, int_bits, frac_bits)
        sys.exit(1)

    # Generate the buffer size for printing
    int_chars = max(1, int(math.ceil(math.log(2**(int_bits-1),10))))
    frac_chars = frac_bits
    sign_char = 1
    point_char = 1
    null_byte = 1
    buffer_length = sign_char + int_chars + point_char + frac_chars + null_byte

    # Generate constants
    fix_inf_pos = 0x2
    point_bits = frac_bits+flag_bits
    pi  = decimal.Decimal('3.1415926535897932385')
    tau = decimal.Decimal('6.2831853071795864769')
    e   = decimal.Decimal('2.7182818284590452354')

    def decimal_to_fix(d):
      t = (d * 2**(point_bits-2))
      t = t.quantize(decimal.Decimal('1.'), rounding=decimal.ROUND_HALF_EVEN)
      t = t * 2**2
      return t
    def decimal_to_fix_extrabits(d, fracbits = point_bits):
      t = (d * 2**(fracbits))
      t = t.quantize(decimal.Decimal('1.'), rounding=decimal.ROUND_HALF_EVEN)
      if t < 0:
          t = Decimal(2**64) + t
      return t

    fix_pi =  fix_inf_pos if int_bits < 3 else decimal_to_fix(pi)
    fix_tau = fix_inf_pos if int_bits < 4 else decimal_to_fix(tau)
    fix_e =   fix_inf_pos if int_bits < 3 else decimal_to_fix(e)

    # Generate LUTs

    def make_c_lut(lut, name):
        l = ["  0x%016x"%(decimal_to_fix_extrabits(x)) for x in lut]
        return "fixed %s[%d] = {\n"%(name, len(lut)) + \
               ",\n".join(l) + \
               "\n};\n"
    def make_c_internal_lut(lut, name):
        l = ["  0x%016x"%(decimal_to_fix_extrabits(x, internal_frac_bits)) for x in lut]
        return "fix_internal %s[%d] = {\n"%(name, len(lut)) + \
               ",\n".join(l) + \
               "\n};\n"
    def make_c_internal_defines(lut, name):
        l = ["#define %s_%d ((fix_internal) 0x%016x)"%(name, i, decimal_to_fix_extrabits(x, internal_frac_bits)) for i,x in enumerate(lut)]
        return "\n".join(l) + "\n"

    # note that 1/0 isn't very useful, so just call it 1
    internal_inv_integer_lut = [Decimal('1')] + [((decimal.Decimal('1')/decimal.Decimal(x))) for x in range(1,25)]
    ln_coef_lut = list(reversed([
           Decimal(x) for x in
             (
                  " -2.12916629329374e-01   2.07162273736410e-01" +
                  " 1.10614715573079e-01  -9.39160505119040e-02" +
                  " -1.22657784290475e-01   1.15022906239994e-01" +
                  " -3.48123672526924e-02   4.20675319814368e-02" +
                  " -6.63978785015256e-02 6.95989625286653e-02" +
                  " -7.09327042396458e-02   7.65806493790257e-02" +
                  " -8.33761981442521e-02   9.09357075253261e-02" +
                  " -9.99975222972258e-02   1.11109768886217e-01" +
                  " -1.25000092157939e-01   1.42857184471956e-01" +
                  " -1.66666664613740e-01   1.99999999280906e-01" +
                  " -2.50000000023946e-01   3.33333333339082e-01" +
                  " -4.99999999999885e-01   9.99999999999986e-01" +
                  " -2.46299846202170e-16"
             ).split(" ")
            if x != ''
        ]))

    # p = polyfit( x, log2(x+1), 25)
    # log2(max(abs(polyval(p, x) - log2(1+x))))
    #   ans = -48.2995602818589
    log2_coef_lut = list(reversed([
           Decimal(x) for x in
             (
                 "  3.07679961935131e-01  -3.06243079996659e-01" +
                 " -1.73489948661271e-01   1.58143550271147e-01" +
                 " 1.83454234803642e-01  -1.75946715460707e-01" +
                 " 4.14035547465458e-02  -5.06459338698202e-02" +
                 " 9.17934127595159e-02  -9.56765593450457e-02" +
                 " 9.52218943362460e-02  -1.02355602112975e-01" +
                 " 1.11068563761742e-01  -1.20283738666059e-01" +
                 " 1.31148001951878e-01  -1.44266155926925e-01" +
                 " 1.60299719510462e-01  -1.80337000893954e-01" +
                 " 2.06099283912046e-01  -2.40449170902889e-01" +
                 " 2.88539008302871e-01  -3.60673760250848e-01" +
                 " 4.80898346961998e-01  -7.21347520444340e-01" +
                 " 1.44269504088897e+00  -7.10448759678215e-16"
             ).split(" ")
            if x != ''
        ]))

    # p = polyfit( x, log10(x+1), 24)
    # log2(max(abs(polyval(p, x) - log10(1+x))))
    #    ans = -48.6780719051126
    log10_coef_lut = list(reversed([
           Decimal(x) for x in
             (

                 "  -9.34517550340438e-02   8.98298668286279e-02" +
                 " 4.95387775517212e-02  -4.05889092899136e-02   " +
                 " -5.42562373254356e-02   4.98302352344150e-02  " +
                 " -1.47518089479240e-02   1.83140760046903e-02  " +
                 " -2.89210571093760e-02   3.02163068148154e-02  " +
                 " -3.07931040695466e-02   3.32600850755936e-02  " +
                 " -3.62110089768021e-02   3.94927223523808e-02  " +
                 " -4.34283051806530e-02   4.82543694777421e-02  " +
                 " -5.42868520978555e-02   6.20420865245062e-02  " +
                 " -7.23824127625090e-02   8.68588960766508e-02  " +
                 " -1.08573620484781e-01   1.44764827303499e-01  " +
                 " -2.17147240951600e-01   4.34294481903245e-01  " +
                 " -8.37288532635468e-17"

             ).split(" ")
            if x != ''
        ]))

    # Write files

    if args["pyfile"] is not None:
        with args["pyfile"] as f:
            f.write("flag_bits = %d\n" %( flag_bits ))
            f.write("int_bits = %d\n" %( int_bits ))
            f.write("frac_bits = %d\n" %( frac_bits ))
            f.write("internal_frac_bits = %d\n"%(internal_frac_bits));
            f.write("internal_int_bits = %d\n"%(internal_int_bits));

    if args["file"] is not None:
        with args["file"] as f:
          baseh = """/*********
 * This file is autogenerated by generate_base.py.
 * Please don't modify it manually.
 *********/

#ifndef base_h
#define base_h

#include <stdint.h>
#include <inttypes.h>

typedef uint64_t fixed;

#define FIX_PRINT_BUFFER_SIZE %d

#define FIX_PRINTF_HEX "%%016"PRIx64
#define FIX_PRINTF_DEC "%%"PRId64

#define FIX_FLAG_BITS %d
#define FIX_FRAC_BITS %d
#define FIX_INT_BITS  %d
#define FIX_BITS (8*sizeof(fixed))

#define FIX_INTERN_FRAC_BITS %d
#define FIX_INTERN_INT_BITS %d

static const fixed fix_pi = 0x%016x;
static const fixed fix_tau = 0x%016x;
static const fixed fix_e = 0x%016x;

#define FIX_PI fix_pi
#define FIX_TAU fix_tau
#define FIX_E fix_e

#endif"""%(buffer_length, flag_bits, frac_bits, int_bits,
           internal_frac_bits, internal_int_bits,
           fix_pi,fix_tau,fix_e)
          f.write(baseh)

    if args["lutfile"] is not None:
        with args["lutfile"] as f:
            lutc  = '#ifndef LUT_H\n'
            lutc += '#define LUT_H\n'
            lutc += '\n'
            lutc += '#include "base.h"\n'
            lutc += '#include "internal.h"\n'
            lutc += "\n"
            lutc += (make_c_internal_lut(internal_inv_integer_lut, "LUT_int_inv_integer"))
            lutc += "\n"
            lutc += (make_c_internal_defines(ln_coef_lut, "FIX_LN_COEF"))
            lutc += "\n"
            lutc += (make_c_internal_defines(log2_coef_lut, "FIX_LOG2_COEF"))
            lutc += "\n"
            lutc += (make_c_internal_defines(log10_coef_lut, "FIX_LOG10_COEF"))
            lutc += "\n#endif\n"
            f.write(lutc)

