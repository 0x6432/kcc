#define CHECK static_assert
CHECK(1, "message" "\0tail");
_Static_assert(1ULL << 63);
