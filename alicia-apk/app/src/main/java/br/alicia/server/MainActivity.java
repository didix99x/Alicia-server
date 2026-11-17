package br.alicia.server;

import android.Manifest;
import android.app.AlertDialog;
import android.content.Context;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.view.KeyEvent;
import android.view.View;
import android.webkit.PermissionRequest;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.EditText;
import android.widget.ImageButton;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

/**
 * Alicia Server — app que só mostra o painel web do servidor numa WebView.
 * O endereço fica salvo no aparelho (botão ⚙ ou tecla MENU), então dá para mudar sem gerar outro APK.
 */
public class MainActivity extends AppCompatActivity {
    private WebView web;
    private SharedPreferences prefs;
    private PermissionRequest pedidoMicrofone;

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        setContentView(R.layout.activity_main);
        prefs = getSharedPreferences("alicia", Context.MODE_PRIVATE);
        web = findViewById(R.id.web);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        web.setWebViewClient(new WebViewClient() {
            @Override
            public void onReceivedError(WebView v, int code, String desc, String url) {
                v.loadData("<body style='background:#0f1117;color:#e9ecf5;font-family:sans-serif;padding:24px;font-size:22px'>"
                        + "<h2>Não consegui falar com o Alicia Server</h2>"
                        + "<p>Confira se o servidor está ligado, se a rede privada (Tailscale) está conectada "
                        + "e se o endereço está certo (botão ⚙).</p></body>", "text/html; charset=utf-8", null);
            }
        });
        // Microfone (voz da Alicia): pede a permissão do Android só quando a página pedir.
        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onPermissionRequest(PermissionRequest r) {
                runOnUiThread(() -> {
                    if (ContextCompat.checkSelfPermission(MainActivity.this, Manifest.permission.RECORD_AUDIO)
                            == PackageManager.PERMISSION_GRANTED) {
                        r.grant(r.getResources());
                    } else {
                        pedidoMicrofone = r;
                        ActivityCompat.requestPermissions(MainActivity.this, new String[]{Manifest.permission.RECORD_AUDIO}, 7);
                    }
                });
            }
        });
        ImageButton cfg = findViewById(R.id.config);
        cfg.setOnClickListener(v -> pedirEndereco());
        if (prefs.getString("url", "").isEmpty()) pedirEndereco(); else abrir();
    }

    @Override
    public void onRequestPermissionsResult(int code, String[] p, int[] r) {
        super.onRequestPermissionsResult(code, p, r);
        if (pedidoMicrofone != null) {
            if (r.length > 0 && r[0] == PackageManager.PERMISSION_GRANTED) pedidoMicrofone.grant(pedidoMicrofone.getResources());
            else pedidoMicrofone.deny(); // sem microfone (ex.: TV box): a conversa por texto continua funcionando
            pedidoMicrofone = null;
        }
    }

    private void abrir() {
        web.loadUrl(prefs.getString("url", ""));
    }

    private void pedirEndereco() {
        EditText campo = new EditText(this);
        campo.setHint("http://100.x.x.x:8080  (IP da rede privada)");
        campo.setText(prefs.getString("url", "http://"));
        new AlertDialog.Builder(this)
                .setTitle("Endereço do Alicia Server")
                .setMessage("Digite o endereço com a porta. Ex.: http://IP-DO-SERVIDOR:8080 (em casa) ou o IP da rede privada.")
                .setView(campo)
                .setPositiveButton("Salvar", (d, w) -> {
                    String u = campo.getText().toString().trim();
                    if (!u.startsWith("http")) u = "http://" + u;
                    prefs.edit().putString("url", u).apply();
                    abrir();
                })
                .setNegativeButton("Cancelar", null)
                .show();
    }

    @Override
    public boolean onKeyDown(int k, KeyEvent e) {
        if (k == KeyEvent.KEYCODE_MENU) { pedirEndereco(); return true; }          // controle remoto da TV box
        if (k == KeyEvent.KEYCODE_BACK && web.canGoBack()) { web.goBack(); return true; }
        return super.onKeyDown(k, e);
    }
}
