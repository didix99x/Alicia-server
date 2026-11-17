plugins {
    id("com.android.application")
}

android {
    namespace = "br.alicia.server"
    compileSdk = 34

    defaultConfig {
        applicationId = "br.alicia.server"
        minSdk = 24            // Android 7.0+ (cobre TV boxes antigas)
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"
    }

    // Assinatura: lê keystore.properties (veja COMPILAR_NO_PC.md). Sem o arquivo, gera APK sem assinar.
    val ksFile = rootProject.file("keystore.properties")
    if (ksFile.exists()) {
        val p = java.util.Properties().apply { load(ksFile.inputStream()) }
        signingConfigs {
            create("alicia") {
                storeFile = rootProject.file(p["storeFile"] as String)
                storePassword = p["storePassword"] as String
                keyAlias = p["keyAlias"] as String
                keyPassword = p["keyPassword"] as String
            }
        }
        buildTypes { getByName("release") { signingConfig = signingConfigs.getByName("alicia") } }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

dependencies {
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("androidx.core:core:1.13.1")
}
