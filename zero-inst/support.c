#include <stdlib.h>
#include <stdio.h>
#include <fcntl.h>
#include <string.h>
#include <assert.h>

#include "support.h"

void *my_malloc(size_t size)
{
	void *new;

	new = malloc(size);
	if (!new) {
		fprintf(stderr, "zero-install: Out of memory");
		return NULL;
	}

	return new;
}

void *my_realloc(void *old, size_t size)
{
	void *new;

	new = realloc(old, size);
	if (!new) {
		fprintf(stderr, "zero-install: Out of memory");
		return NULL;
	}

	return new;
}

char *my_strdup(const char *str)
{
	int l = strlen(str) + 1;
	char *new;

	new = my_malloc(l);
	if (!new)
		return NULL;
		
	memcpy(new, str, l);

	return new;
}

void set_blocking(int fd, int blocking)
{
	if (fcntl(fd, F_SETFL, blocking ? 0 : O_NONBLOCK))
		perror("fcntl() failed");
}

/* Copy uri to buffer. If uri is relative, store the absolute path
 * in buffer, using the given base URI.
 * 'http://foo.org/dir', 'leaf.html' -> 'http://foo.org/dir/leaf.html'
 * 'http://foo.org/dir', 'http://bar.org/leaf' -> 'http://bar.org/leaf'
 *
 * 0 on success.
 */
int uri_ensure_absolute(char *uri, int len, const char *base)
{
	int base_len, uri_len;

	if (strncmp(uri, "ftp://", 6) == 0 ||
	    strncmp(uri, "http://", 7) == 0 ||
	   strncmp(uri, "https://", 8) == 0) {
		printf("Absolute path\n");
		return 1;
	}

	/* Relative path */
	printf("Join '%s' + '%s'\n", base, uri);

	uri_len = strlen(uri);
	base_len = strlen(base);

	if (uri_len + base_len + 2 > len) {
		fprintf(stderr, "URI too long\n");
		return 0;
	}

	memmove(uri + base_len + 1, uri, uri_len + 1);
	uri[base_len] = '/';
	memcpy(uri, base, base_len);

	return 1;
}

/* /http/www.foo.org/some/path, one, two to
 * http://www.foo.org/some/path/one/two
 *
 * The two 'leaf' components are appended, if non-NULL.
 * 0 on error, which will have been already reported.
 */
int build_uri(char *buffer, int len, const char *path,
		     const char *leaf1, const char *leaf2)
{
	int n;
	char *slash;

	assert(path[0] == '/');
	path++;

	slash = strchr(path, '/');
	assert(slash != NULL && slash != path);

	n = slash - path;	/* Length of protocol (http=4) */
	if (n > len)
		goto too_big;
	memcpy(buffer, path, n);
	path += n;
	buffer += n;
	len -= n;

	if (snprintf(buffer, len, ":/%s%s%s%s%s", path,
			leaf1 ? "/" : "", leaf1 ? leaf1 : "",
			leaf2 ? "/" : "", leaf2 ? leaf2 : "") > len - 1)
		goto too_big;

	return 1;
too_big:
	fprintf(stderr, "Path '%s' too long to convert to URI\n", path);
	return 0;
}
