#!/usr/bin/env python
import unittest
import os, signal, time
import traceback
import mmap

version = '0.1.23'.replace('.', 'd')

verbose = False

fs = os.path.expanduser('~/test/0install')
cache = os.path.expanduser('~/test/cache')

if os.path.ismount(fs):
	os.system("sudo umount " + fs)
	assert not os.path.ismount(fs)

os.system("sudo rmmod lazyfs" + version)

if not os.path.isdir(fs):
	raise Exception('Create %s first' % fs)
if not os.path.isdir(cache):
	raise Exception('Create %s first' % cache)
uid = os.geteuid()
cache_uid = os.stat(cache).st_uid 
if cache_uid != uid:
	raise Exception('%s must be owned by user %s (not %s)' %
			(cache, uid, cache_uid))

class LazyFS(unittest.TestCase):
	def setUp(self):
		for item in os.listdir(cache):
			os.system("rm -r '%s'" % os.path.join(cache, item))
		os.system("sudo mount -t lazyfs%s lazyfs %s -o %s" % (version, fs, cache))

	def tearDown(self):
		os.system("sudo umount " + fs)
	
def cstest(base):
	def test(self):
		assert self.c is not None
		client = getattr(self, 'client' + base)
		server = getattr(self, 'server' + base)
		child = os.fork()
		if child == 0:
			try:
				os.close(self.c)
				self.c = None
				client()
			except:
				print "Error from client:"
				traceback.print_exc()
				os._exit(1)
			os._exit(0)
		else:
			try:
				server()
				error = None
			except Exception, ex:
				error = ex
			for x in range(10):
				died, status = os.waitpid(child, os.WNOHANG)
				if died == child:
					if status and not error:
						error = Exception('Error in child')
					break
				time.sleep(0.1)
			else:
				print "Killing", child
				os.kill(child, signal.SIGTERM)
				os.waitpid(child, 0)
				if not error:
					error = Exception('Error in child')
			if error:
				raise error or Exception("Child didn't quit")
	return test

class WithHelper(LazyFS):
	def setUp(self):
		LazyFS.setUp(self)
		self.c = os.open(fs + '/.lazyfs-helper', os.O_RDONLY)
	
	def tearDown(self):
		if self.c is not None:
			os.close(self.c)
		self.c = None
		LazyFS.tearDown(self)

class Test1WithoutHelper(LazyFS):
	def test1CacheLink(self):
		assert os.path.islink(fs + '/.lazyfs-cache')
		assert os.readlink(fs + '/.lazyfs-cache') == cache
	
	def test2UnconnectedEmpty(self):
		try:
			file(fs + '/f')
			assert 0
		except IOError:
			pass

class Test2WithHelper(WithHelper):
	def read_rq(self):
		if verbose:
			print "Reading request..."
		fd = os.read(self.c, 1000)
		return int(fd.split(' ', 1)[0])
	
	def next(self):
		fd = self.read_rq()
		path = os.read(fd, 1000)
		assert path[-1] == '\0'
		return (fd, path[:-1])
	
	def assert_ls(self, dir, ls):
		real = os.listdir(dir)
		#os.system("dmesg| tail -15")
		real.sort()
		ls = ls[:]
		ls.sort()
		self.assertEquals(ls, real)

	def clientNothing(self): pass
	def serverNothing(self): pass
	test1Nothing = cstest('Nothing')
	
	def clientReleaseHelper(self):
		os.open(fs + '/.lazyfs-helper', os.O_RDONLY)
	
	def serverReleaseHelper(self):
		os.close(self.c)
		self.c = None

	test2ReleaseHelper = cstest('ReleaseHelper')
	
	def clientDoubleOpen(self):
		# Check that we can't open the helper a second time
		try:
			c = os.open(fs + '/.lazyfs-helper', os.O_RDONLY)
			assert 0
		except OSError:
			pass

	def serverDoubleOpen(self):
		# This is a request for /. Ignore it.
		fd = self.read_rq()
		os.close(fd)

	test3DoubleOpen = cstest('DoubleOpen')

	def clientLsRoot(self):
		self.assert_ls(fs, ['.lazyfs-helper', '.lazyfs-cache'])
	def serverLsRoot(self):
		self.send_dir('/', [])

	test4LsRoot = cstest('LsRoot')

	def clientGetROX(self):
		self.assert_ls(fs + '/rox', ['apps'])
	
	def serverGetROX(self):
		fd, path = self.next()
		self.assertEquals('/', path)
		f = file(cache + '/...', 'w').write('LazyFS\nd 1 1 rox\0')
		os.close(fd)

		fd, path = self.next()
		self.assertEquals('/rox', path)
		os.mkdir(cache + '/rox')
		f = file(cache + '/rox/...', 'w').write('LazyFS\nd 1 1 apps\0')
		os.close(fd)
	
	test5GetROX = cstest('GetROX')

	def put_dir(self, dir, contents):
		"""contents is None for a dynamic directory"""
		f = file(cache + dir + '/....', 'w')
		if contents is None:
			f.write('LazyFS Dynamic\n')
		elif contents:
			f.write('LazyFS\n' + '\0'.join(contents) + '\0')
		else:
			f.write('LazyFS\n')
		f.close()
		os.rename(cache + dir + '/....', cache + dir + '/...')

	def send_dir(self, dir, contents = None):
		assert dir.startswith('/')
		fd, path = self.next()
		if verbose:
			print "Got request for ", dir
		self.assertEquals(dir, path)
		self.put_dir(dir, contents)
		os.close(fd)
	
	def send_file(self, rq, contents, mtime):
		assert rq.startswith('/')
		if verbose:
			print "Expecting", rq
		fd, path = self.next()
		self.assertEquals(rq, path)
		f = file(cache + rq, 'w')
		f.write(contents)
		f.close()
		os.utime(cache + rq, (mtime, mtime))
		os.close(fd)

	def send_reject(self, rq):
		assert rq.startswith('/')
		fd, path = self.next()
		self.assertEquals(rq, path)
		if verbose:
			print "Rejecting", rq
		os.close(fd)

	def clientDownload(self):
		assert not os.path.exists(cache + '/...')
		self.assert_ls(fs + '/', ['.lazyfs-cache', '.lazyfs-helper', 'hello'])
		self.assertEquals('Hello', file(fs + '/hello').read())
		self.assertEquals('Hello', file(fs + '/hello').read())
		os.unlink(cache + '/hello')
		self.assertEquals('World', file(fs + '/hello').read())
		self.put_dir('/', ['f 6 3 hello'])
		self.assertEquals('Worlds', file(fs + '/hello').read())
	
	def serverDownload(self):
		self.send_dir('/', ['f 5 3 hello'])
		self.send_file('/hello', 'Hello', 3)
		self.send_file('/hello', 'World', 3)
		self.send_file('/hello', 'Worlds', 3)

	test6Download = cstest('Download')

	def clientDynamic(self):
		assert not os.path.exists(cache + '/...')
		self.assert_ls(fs + '/', ['.lazyfs-cache', '.lazyfs-helper'])
		assert os.path.isdir(fs + '/dir')
		self.assert_ls(fs + '/dir', ['hello'])
		assert os.path.isdir(cache + '/dir')
		os.spawnlp(os.P_WAIT, 'rm', 'rm', '-r', '--', cache + '/dir')
		assert not os.path.isdir(cache + '/dir')
		assert not os.path.isdir(fs + '/dir')
		assert not os.path.isdir(fs + '/foo')
	
	def serverDynamic(self):
		self.send_dir('/')
		os.mkdir(cache + '/dir')
		self.send_dir('/dir', ['f 5 3 hello'])
		self.send_reject('/dir')
		self.send_reject('/dir')
		self.send_reject('/foo')
		
	test7Dynamic = cstest('Dynamic')

	def clientMMap1(self):
		# File is changed in-place
		fd = os.open(fs + '/hello', os.O_RDONLY)
		m = mmap.mmap(fd, 5, mmap.MAP_SHARED, mmap.PROT_READ)
		os.close(fd)
		self.assertEquals('Hello', m[:])
		self.put_dir('/', ['f 6 3 hello'])
		file(fs + '/hello').read()	# Force update
		self.assertEquals('Worlds', file(cache + '/hello').read())
		self.assertEquals('World', m[:])
	
	def serverMMap1(self):
		self.send_dir('/', ['f 5 3 hello'])
		self.send_file('/hello', 'Hello', 3)
		self.send_file('/hello', 'Worlds', 3)

	test8MMap1 = cstest('MMap1')

	def clientMMap2(self):
		# A new file is created
		fd = os.open(fs + '/hello', os.O_RDONLY)
		m = mmap.mmap(fd, 5, mmap.MAP_SHARED, mmap.PROT_READ)
		os.close(fd)
		self.assertEquals('Hello', m[:])
		self.put_dir('/', ['f 6 3 hello'])
		os.unlink(cache + '/hello')
		self.assertEquals('Worlds', file(fs + '/hello').read())
		self.assertEquals('Hello', m[:])

		fd = os.open(fs + '/hello', os.O_RDONLY)
		m2 = mmap.mmap(fd, 5, mmap.MAP_SHARED, mmap.PROT_READ)
		self.assertEquals('Hello', m[:])
		self.assertEquals('World', m2[:])
		os.close(fd)
	
	serverMMap2 = serverMMap1
	
	test8MMap2 = cstest('MMap2')

	def clientMMap3(self):
		# A new file is created in the cache, but the lazyfs
		# inode remains the same.
		# We can't support this, because Linux mappings are
		# per-inode, not per-open-file, however we make sure the kernel
		# handles it gracefully (newer 2.6 kernels may provide a way to
		# fix the underlying problem, but it's not a big issue).
		fd = os.open(fs + '/hello', os.O_RDONLY)
		m = mmap.mmap(fd, 5, mmap.MAP_SHARED, mmap.PROT_READ)
		os.close(fd)
		self.assertEquals('Hello', m[:])
		os.unlink(cache + '/hello')
		self.assertEquals('World', file(fs + '/hello').read())
		self.assertEquals('Hello', m[:])

		fd = os.open(fs + '/hello', os.O_RDONLY)
		try:
			mmap.mmap(fd, 5, mmap.MAP_SHARED, mmap.PROT_READ)
			assert False
		except (IOError, EnvironmentError):
			# (I think EnvironmentError is a Python bug; it should
			# report the -EBUSY from mmap, but it actually reports
			# the error from the following msync)
			pass
		self.assertEquals('Hello', m[:])
		os.close(fd)
	
	def serverMMap3(self):
		self.send_dir('/', ['f 5 3 hello'])
		self.send_file('/hello', 'Hello', 3)
		self.send_file('/hello', 'World', 3)
	
	test8MMap3 = cstest('MMap3')
	
if __name__ == '__main__':
	import sys
	sys.argv.append('-v')
	unittest.main()
