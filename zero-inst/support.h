void *my_malloc(size_t size);
void *my_realloc(void *old, size_t size);
char *my_strdup(const char *str);
void set_blocking(int fd, int blocking);
int build_uri(char *buffer, int len, const char *path,
		     const char *leaf1, const char *leaf2);
int uri_ensure_absolute(char *uri, int len, const char *base);