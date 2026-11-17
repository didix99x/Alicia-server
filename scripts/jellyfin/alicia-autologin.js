// Alicia Server: entra sozinho como o usuário "casa" (sem senha) quando este navegador ainda não tem login no Jellyfin.
// Para entrar como outro usuário (ex.: administrador), abra o endereço com ?manual=1  (ex.: http://IP-DO-SERVIDOR:8096/?manual=1).
(function () {
  try {
    if (location.search.indexOf('manual=1') >= 0) { sessionStorage.setItem('alicia_manual', '1'); }
    if (sessionStorage.getItem('alicia_manual') === '1') return;
    var k = 'jellyfin_credentials', c = null;
    try { c = JSON.parse(localStorage.getItem(k) || 'null'); } catch (e) {}
    if (c && c.Servers && c.Servers.length && c.Servers[0].AccessToken) return;      // já tem login
    var get = function (url) { var x = new XMLHttpRequest(); x.open('GET', url, false); x.send(); return JSON.parse(x.responseText); };
    var info = get('/System/Info/Public');
    var id = localStorage.getItem('_deviceId2') || ('alicia-' + Math.random().toString(36).slice(2) + Date.now().toString(36));
    localStorage.setItem('_deviceId2', id);
    var x = new XMLHttpRequest(); x.open('POST', '/Users/AuthenticateByName', false);
    x.setRequestHeader('Content-Type', 'application/json');
    x.setRequestHeader('Authorization', 'MediaBrowser Client="Jellyfin Web", Device="Navegador", DeviceId="' + id + '", Version="1.0"');
    x.send(JSON.stringify({ Username: 'casa', Pw: '' }));
    if (x.status !== 200) return;
    var a = JSON.parse(x.responseText);
    localStorage.setItem(k, JSON.stringify({ Servers: [{
      ManualAddress: location.origin, Id: info.Id, Name: info.ServerName, UserId: a.User.Id, AccessToken: a.AccessToken,
      DateLastAccessed: Date.now(), LastConnectionMode: 2 }] }));
  } catch (e) { /* se algo falhar, aparece a tela de login normal */ }
})();
