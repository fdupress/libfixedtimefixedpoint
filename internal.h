#ifndef internal_h
#define internal_h

#include "base.h"

// This file contains things needed internally for libftfp, but that a library
// user should never need to see.

///////////////////////////////////////
//  Useful Defines
///////////////////////////////////////

#define FIX_FLAGS_MASK 0x3

#define FIX_POINT_BITS (FIX_FRAC_BITS + FIX_FLAG_BITS)

#define FIX_ALL_BIT_MASK 0xffffffff
#define FIX_TOP_BIT_MASK (1<<31)
#define FIX_TOP_BIT(f) ((f) & FIX_TOP_BIT_MASK)

#define FIX_FRAC_MASK (((1<<(FIX_FRAC_BITS))-1) << (FIX_FLAG_BITS))
#define FIX_INT_MASK  (((1<<(FIX_INT_BITS))-1) << ((FIX_FLAG_BITS) + (FIX_FRAC_BITS)))

#define FIX_SIGN_TO_64(f) ((int64_t)((int32_t)(f)))

#define SIGN_EXTEND(value, n_top_bit) ({uint32_t SE_m__ = (1 << ((n_top_bit)-1)); (((uint32_t) (value)) ^ SE_m__) - SE_m__;})
#define SIGN_EX_SHIFT_RIGHT_32(value, shift) SIGN_EXTEND( (value) >> (shift), 32 - (shift) )
#define MASK_UNLESS(expression, value) (SIGN_EXTEND(!!(expression), 1) & (value))

#define FIX_DATA_BIT_MASK (0xFFFFFFFC)
#define FIX_DATA_BITS(f) ((f) & FIX_DATA_BIT_MASK)

#define FIX_IF_NAN(isnan) (((isnan) | ((isnan) << 1)) & FIX_NAN)
#define FIX_IF_INF_POS(isinfpos) (((isinfpos) | ((isinfpos) << 1)) & FIX_INF_POS)
#define FIX_IF_INF_NEG(isinfneg) (((isinfneg) | ((isinfneg) << 1)) & FIX_INF_NEG)

/* Lops off the rightmost n_shift_bits of value and rounds to an even value
 * (so 0.5 will round to 0, but 1.5 will round to 2)
 *
 * n_shift_bits must be >- 2.
 *
 * Round Truth table:
 *  Bit 0 1 2       Result
 *      0 0 0       0 0x0
 *      0 0 1       0 0x0
 *      0 1 0       0 0x0
 *      0 1 1       1 0x1
 *      1 0 0       0 0x1
 *      1 0 1       0 0x1
 *      1 1 0       1 0x2
 *      1 1 1       1 0x2
 * The repeated phrase
 *
 *    ((!!(value & ((1 << (n_shift_bits-1))-1))) << (n_shift_bits-1))
 *
 *  is there to compress all lower-order bits into bit 2 in the truth table
 * */
#define ROUND_TO_EVEN(value, n_shift_bits) \
  (((value) >> (n_shift_bits)) + \
   !!( \
     (!!((value) & (1 << ((n_shift_bits)-1))) & !!((value) & ((1 << ((n_shift_bits)-1))-1))) | \
     ((((value) >> ((n_shift_bits)-2)) & 0x6) == 0x6) \
   ))

#define ROUND_TO_EVEN_SIGNED(value, n_shift_bits) \
  (SIGN_EX_SHIFT_RIGHT_32(value, n_shift_bits) + \
   !!( \
     (!!((value) & (1 << ((n_shift_bits)-1))) & !!((value) & ((1 << ((n_shift_bits)-1))-1))) | \
     ((((value) >> ((n_shift_bits)-2)) & 0x6) == 0x6) \
   ))


/*
 * General idea:
 *   This creates the fractional portion of a fixed point, given a decimal
 *   fraction. It uses the formula:
 *
 *     "one" / 10^( ceil(log_10( frac )) ) * frac
 *
 *  Along with extra precision bits and rounding to get as close as possible. It
 *  actually looks more like, with rounding tacked on:
 *
 *   (((1<<(FIX_FRAC_BITS+15)) / ((int) pow(10, log_ceil))) * frac >> 15) << FIX_FLAG_BITS;
 *
 * Notes:
 *   This works fairly well, and should always give the fixed point that is
 *   closest to the decimal number .frac. That is, FIXFRAC(5) will give 0.5,
 *   etc. We use a horrible strlen preprocessor trick, so FIXFRAC(001) will
 *   give a fixed point close to 0.001.
 *
 *   I'd really like to remove the pow call; doing this in the preprocessor
 *   seems difficult.
 *
 *   To prevent octal assignment, we do some nonsense into frac_int.
 */
#define FIXFRAC(frac) ({ \
    uint32_t bits = 4; \
    uint64_t log_ceil = ((uint64_t) strlen( #frac )); \
    uint64_t one = 1ULL << (FIX_FRAC_BITS + bits); \
    uint64_t p = (uint64_t) pow(10, log_ceil); \
    uint64_t frac_int =  1 ## frac - ((int64_t) pow(10, log_ceil)); \
    uint64_t n = (frac_int * one) / p; \
    ((ROUND_TO_EVEN(n, bits)) << FIX_FLAG_BITS); \
    })

#define FIXINT(z) ((z)<<(FIX_FLAG_BITS+FIX_FRAC_BITS))

/* We do this stupid nosign thing to prevent FIX_MAX from rolling over into the
 * negative. It 'rounds' to FIX_MAX + 1 == FIX_MIN, which causes trouble.
 * There's gotta be a better way... */

#define FIX_ROUND_BASE(op1, round_exp) ({ \
    uint8_t isinfpos = FIX_IS_INF_POS(op1); \
    uint8_t isinfneg = FIX_IS_INF_NEG(op1); \
    uint8_t isnan = FIX_IS_NAN(op1); \
    uint8_t isneg = FIX_IS_NEG(op1); \
    uint8_t ex = isinfpos | isinfneg | isnan; \
    uint32_t result_nosign = round_exp; \
    uint32_t result = SIGN_EXTEND(result_nosign, FIX_INT_BITS); \
    (MASK_UNLESS(isinfpos, INT_MAX) | \
     MASK_UNLESS(isinfneg, INT_MIN) | \
     MASK_UNLESS(isneg  & !ex, result) | \
     MASK_UNLESS(!isneg & !ex, result_nosign)); \
    })

/* Uses round to even semantics */
#define FIX_ROUND_INT(op1) \
    FIX_ROUND_BASE(op1, ROUND_TO_EVEN(op1, FIX_FLAG_BITS + FIX_FRAC_BITS))

/* 0.5 rounds up always */
#define FIX_ROUND_UP_INT(op1) \
  FIX_ROUND_BASE(op1, (((op1) >> (FIX_FLAG_BITS + FIX_FRAC_BITS)) + (op1 >> (FIX_FLAG_BITS + FIX_FRAC_BITS-1) & 0x1)))

#define FIX_CEIL(op1) \
  FIX_ROUND_BASE(op1, ((op1) >> (FIX_FLAG_BITS + FIX_FRAC_BITS)) + !!(op1 & FIX_FRAC_MASK))

#define FIX_FLOOR(op1) \
  FIX_ROUND_BASE(op1, ((op1) >> (FIX_FLAG_BITS + FIX_FRAC_BITS)))



///////////////////////////////////////
//  Useful Arithmetic
///////////////////////////////////////

// ensure that we never divide by 0. Caller is responsible for checking.
#define FIX_UNSAFE_DIV_32(op1, op2) \
  (ROUND_TO_EVEN(((FIX_SIGN_TO_64(FIX_DATA_BITS(op1))<<32) / \
                   FIX_SIGN_TO_64((op2) | (FIX_DATA_BITS(op2) == 0))),FIX_POINT_BITS)<<2)

// Note that you will lose the bottom bit of op2 for overflow safety
// Shift op2 right by 2 to gain 2 extra overflow bits
#define FIX_DIV_32(op1, op2, overflow) \
  ({ \
    uint64_t fdiv32tmp = FIX_UNSAFE_DIV_32(op1, \
      SIGN_EX_SHIFT_RIGHT_32(op2, 1)); \
    uint64_t masked = fdiv32tmp & 0xFFFFFFFF00000000; \
    overflow = !((masked == 0xFFFFFFFF00000000) | (masked == 0)); \
    (fdiv32tmp >> 1) & 0xffffffff; \
  })

// Sign extend it all, this will help us correctly catch overflow
#define FIX_UNSAFE_MUL_32(op1, op2) \
  (ROUND_TO_EVEN(FIX_SIGN_TO_64(op1) * FIX_SIGN_TO_64(op2),17))

#define FIX_MUL_32(op1, op2, overflow) \
  ({ \
    uint64_t tmp = FIX_UNSAFE_MUL_32(op1, op2); \
    /* inf only if overflow, and not a sign thing */ \
    overflow |= \
      !(((tmp & 0xFFFFFFFF80000000) == 0xFFFFFFFF80000000) \
       | ((tmp & 0xFFFFFFFF80000000) == 0)); \
    tmp; \
   })

// Multiply two 2.28 bit fixed point numbers
#define MUL_2x28(op1, op2) ((uint32_t) ((((int64_t) ((int32_t) (op1)) ) * ((int64_t) ((int32_t) (op2)) )) >> (32-4)) & 0xffffffff)

///////////////////////////////////////
//  Helper functions
///////////////////////////////////////

uint32_t fix_circle_frac(fixed op1);
uint32_t uint32_log2(uint32_t o);

void cordic(uint32_t* Z, uint32_t* C, uint32_t* S);

#endif
