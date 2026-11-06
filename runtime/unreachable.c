/* Reaching C23 unreachable() has undefined behavior. This fallback chooses
 * immediate termination rather than granting the optimizer unreachable facts. */
#include <stdlib.h>

_Noreturn void __kcc_unreachable(void)
{
    abort();
}
