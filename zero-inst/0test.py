#!/usr/bin/env python

import traceback
import os, socket
import time

def unmount():
	if os.path.exists('/uri/0install/.lazyfs-helper'):
		print "Unmounting..."
		os.system('sudo umount /uri/0install')
		if os.path.exists('/uri/0install/.lazyfs-helper'):
			raise Exception("Can't unmount /uri/0install!")
		lines = os.popen('dmesg').readlines()
		lines.reverse()
		#i = lines.index("lazyfs: Resource usage after put_super:\n")
		#for i in range(len(lines)):
		#	if lines[i].startswith("'/' "):
		#		i += 1
		#		break
		lines.reverse()
		print ">> dmesg output"
		#print ''.join(lines[-i:])
		os.system('sudo rmmod lazyfs')

unmount()
os.system('rm -rf /var/cache/zero-inst/0test')
os.system('sudo mount /uri/0install')
tmp = '/tmp'

http = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

for port in range(3000, 3100):
	try:
		http.bind(('localhost', port))
	except socket.error:
		continue
	break
else:
	raise Exception('No available ports!')
http.listen(5)

os.environ['http_proxy'] = 'http://localhost:%d' % port

zero = os.spawnlp(os.P_NOWAIT, './zero-install', './zero-install', '--debug')

def tgz_containing(name, contents):
	file(os.path.join(tmp, name), 'w').write(contents)
	os.system("cd '%s'; rm -f index.xml.sig keyring.pub; gpg -o index.xml.sig --default-key 0install@0test --detach-sign '%s'; gpg -o keyring.pub --export 0install@0test" %
		(tmp, name))
	file(os.path.join(tmp, "mirrors.xml"), 'w').write('Hello')
	os.system('ls /tmp')
	data = os.popen('tar -cz -O -C "%s" "%s" mirrors.xml keyring.pub index.xml.sig' % (tmp, name)).read()
	os.unlink(os.path.join(tmp, name))
	return data

class Request:
	def __init__(self, want_uri):
		#print "waiting..."
		(self.c, addr) = http.accept()
		#print "Got connection", self.c
		data = self.c.recv(1024)
		uri = data.split('\n', 1)[0].split()[1]
		print "[s] Zero-Install requested", uri
		assert uri == want_uri

	def reply(self, message):
		self.c.send('HTTP/1.0 200 OK\n\n')
		self.c.send(tgz_containing('.0inst-index.xml', message))
		self.close()
	
	def close(self):
		self.c.close()

def send_tree(xml, path='/uri/0install/0test'):
	if path is not None:
		path = "path='%s'" % path
	else:
		path = ""
	r = Request('http://0test/.0inst-index.tgz')
	r.reply('<?xml version="1.0"?>\n<site-index xmlns="http://zero-install.sourceforge.net" %s>%s</site-index>' % (path, xml))

def test():
	if not server:
		# Helper might not have started yet...
		time.sleep(0.8)
	import test_cases

child = os.fork()
if child == 0:
	# Child
	try:
		server = False
		test()
		print "All tests passed"
		os._exit(0)
	except:
		traceback.print_exc()
		os._exit(1)
else:
	# Parent
	ok = False
	try:
		server = True
		test()
		ok = True
	except:
		import traceback
		traceback.print_exc()
	
	print "Waiting for test child to finish"
	http.close()
	(pid, status) = os.waitpid(child, 0)
	import signal
	os.kill(zero, signal.SIGINT)
	print "Waiting for zero-install to finish"
	os.waitpid(zero, 0)
	print
	if status:
		print "Error from child (code %d)" % status
	elif not ok:
		print "Failed (server error)"
	else:
		print "All tests passed!"

unmount()
