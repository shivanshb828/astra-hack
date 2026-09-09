import http.client,json,threading,unittest
from unittest.mock import patch
import dashboard
class ConcurrentDashboardTests(unittest.TestCase):
 def test_state_remains_readable_during_slow_mutation(self):
  entered=threading.Event();release=threading.Event();done=[]
  def slow(h,token):
   h.rfile.read(int(h.headers.get('Content-Length','0')))
   entered.set();release.wait(3);h.send_response(200);h.end_headers();h.wfile.write(b'{}')
  def request(method,path):
   c=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=1)
   try:c.request(method,path,body=b'{}' if method=='POST' else None,headers={'Host':'127.0.0.1:8768'});r=c.getresponse();return r.status,r.read()
   finally:c.close()
  server=dashboard.Server(('127.0.0.1',0),dashboard.Handler)
  with patch('assembly_http.post',side_effect=slow),patch('blender_handoff.state',return_value={'connected':True}):
   worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
   post=threading.Thread(target=lambda:done.append(request('POST','/assembly/action')),daemon=True);post.start()
   try:
    self.assertTrue(entered.wait(1));code,body=request('GET','/assembly/state');self.assertEqual(code,200);self.assertTrue(json.loads(body)['connected'])
   finally:release.set();post.join(2);server.shutdown();server.server_close();worker.join(2)
   self.assertEqual(done,[(200,b'{}')])
