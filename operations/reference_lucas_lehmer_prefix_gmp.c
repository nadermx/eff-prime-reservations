/* Exact Lucas--Lehmer prefix oracle using GMP and direct Mersenne reduction. */

#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>

#if __has_include(<gmp.h>)
#include <gmp.h>
#else
/* Debian's runtime image supplies libgmp.so.10 without the development
   header. These are GMP's stable public integer ABI types and the small API
   surface used below; function symbols carry the documented __gmp prefix. */
typedef unsigned long int mp_limb_t;
typedef unsigned long int mp_bitcnt_t;
typedef struct {
    int _mp_alloc;
    int _mp_size;
    mp_limb_t *_mp_d;
} __mpz_struct;
typedef __mpz_struct mpz_t[1];
typedef __mpz_struct *mpz_ptr;
typedef const __mpz_struct *mpz_srcptr;

extern void __gmpz_init(mpz_ptr);
extern void __gmpz_clear(mpz_ptr);
extern void __gmpz_set_ui(mpz_ptr, unsigned long int);
extern void __gmpz_mul_2exp(mpz_ptr, mpz_srcptr, mp_bitcnt_t);
extern void __gmpz_sub_ui(mpz_ptr, mpz_srcptr, unsigned long int);
extern void __gmpz_sub(mpz_ptr, mpz_srcptr, mpz_srcptr);
extern void __gmpz_mul(mpz_ptr, mpz_srcptr, mpz_srcptr);
extern void __gmpz_fdiv_r_2exp(mpz_ptr, mpz_srcptr, mp_bitcnt_t);
extern void __gmpz_fdiv_q_2exp(mpz_ptr, mpz_srcptr, mp_bitcnt_t);
extern void __gmpz_add(mpz_ptr, mpz_srcptr, mpz_srcptr);
extern int __gmpz_cmp(mpz_srcptr, mpz_srcptr);
extern unsigned long int __gmpz_get_ui(mpz_srcptr);
extern unsigned long int __gmpz_fdiv_ui(mpz_srcptr, unsigned long int);
extern size_t __gmpz_sizeinbase(mpz_srcptr, int);
extern size_t __gmpz_out_raw(FILE *, mpz_srcptr);

#define mpz_init __gmpz_init
#define mpz_clear __gmpz_clear
#define mpz_set_ui __gmpz_set_ui
#define mpz_mul_2exp __gmpz_mul_2exp
#define mpz_sub_ui __gmpz_sub_ui
#define mpz_sub __gmpz_sub
#define mpz_mul __gmpz_mul
#define mpz_fdiv_r_2exp __gmpz_fdiv_r_2exp
#define mpz_fdiv_q_2exp __gmpz_fdiv_q_2exp
#define mpz_add __gmpz_add
#define mpz_cmp __gmpz_cmp
#define mpz_get_ui __gmpz_get_ui
#define mpz_fdiv_ui __gmpz_fdiv_ui
#define mpz_sizeinbase __gmpz_sizeinbase
#define mpz_out_raw __gmpz_out_raw
#endif


static void usage(const char *program) {
    fprintf(stderr, "usage: %s EXPONENT ITERATIONS [RAW_STATE]\n", program);
}


static unsigned long parse_unsigned(const char *text, const char *label) {
    char *end = NULL;
    errno = 0;
    unsigned long value = strtoul(text, &end, 10);
    if (errno != 0 || end == text || *end != '\0') {
        fprintf(stderr, "invalid %s: %s\n", label, text);
        exit(64);
    }
    return value;
}


int main(int argc, char **argv) {
    if (argc != 3 && argc != 4) {
        usage(argv[0]);
        return 64;
    }
    const unsigned long exponent = parse_unsigned(argv[1], "exponent");
    const unsigned long iterations = parse_unsigned(argv[2], "iteration count");
    if (exponent <= 2 || (exponent & 1UL) == 0 || iterations == 0) {
        fprintf(stderr, "exponent must be odd and >2; iterations must be positive\n");
        return 64;
    }

    mpz_t modulus, residue, square, low, high;
    mpz_init(modulus);
    mpz_init(residue);
    mpz_init(square);
    mpz_init(low);
    mpz_init(high);
    mpz_set_ui(modulus, 1);
    mpz_mul_2exp(modulus, modulus, exponent);
    mpz_sub_ui(modulus, modulus, 1);
    mpz_set_ui(residue, 4);

    for (unsigned long index = 0; index < iterations; ++index) {
        mpz_mul(square, residue, residue);
        mpz_sub_ui(square, square, 2);

        /* For 0 <= residue < 2^p-1, square-2 < 2^(2p).  Reduction
           modulo 2^p-1 is the exact cyclic fold low + high followed by
           at most one subtraction of the modulus. */
        mpz_fdiv_r_2exp(low, square, exponent);
        mpz_fdiv_q_2exp(high, square, exponent);
        mpz_add(residue, low, high);
        if (mpz_cmp(residue, modulus) >= 0) {
            mpz_sub(residue, residue, modulus);
        }
    }

    const unsigned long res64 = mpz_get_ui(residue);
    const unsigned long mod35 = (1UL << 35) - 1;
    const unsigned long mod36 = (1UL << 36) - 1;
    printf("exponent=%lu\n", exponent);
    printf("iterations=%lu\n", iterations);
    printf("res64=%016" PRIX64 "\n", (uint64_t)res64);
    printf("res_mod_2^35_minus_1=%lu\n", mpz_fdiv_ui(residue, mod35));
    printf("res_mod_2^36_minus_1=%lu\n", mpz_fdiv_ui(residue, mod36));
    printf("residue_bits=%zu\n", mpz_sizeinbase(residue, 2));

    if (argc == 4) {
        FILE *output = fopen(argv[3], "wb");
        if (output == NULL) {
            perror("fopen raw state");
            mpz_clear(modulus);
            mpz_clear(residue);
            mpz_clear(square);
            mpz_clear(low);
            mpz_clear(high);
            return 74;
        }
        if (mpz_out_raw(output, residue) == 0 || fclose(output) != 0) {
            perror("write raw state");
            mpz_clear(modulus);
            mpz_clear(residue);
            mpz_clear(square);
            mpz_clear(low);
            mpz_clear(high);
            return 74;
        }
    }

    mpz_clear(modulus);
    mpz_clear(residue);
    mpz_clear(square);
    mpz_clear(low);
    mpz_clear(high);
    return 0;
}
