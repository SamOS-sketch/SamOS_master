
const { SamOSClient } = require('./index');

(async () => {
  const c = new SamOSClient({ baseUrl: 'http://localhost:8000' });
  const session = await c.startSession();
  const sid = session.session_id;
  console.log('Session:', session);

  console.log('Mode before:', await c.getMode(sid));
  console.log('Set mode to sandbox:', await c.setMode(sid, 'sandbox'));

  await c.putMemory(sid, 'demo.note', 'hello from node', { source: 'poc' });
  console.log('Memory get:', await c.getMemory(sid, 'demo.note'));
  console.log('Image:', await c.generateImage(sid, 'sunrise over calm sea'));
  console.log('EMMs:', await c.listEmms(sid, 5));
})().catch(e => { console.error(e); process.exit(1); });
