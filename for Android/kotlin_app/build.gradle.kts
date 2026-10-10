import java.io.File

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    id("com.chaquo.python") version "17.0.0"
}

val externalSigning = listOf("AGENT_ANDROID_KEYSTORE", "AGENT_ANDROID_KEY_ALIAS",
    "AGENT_ANDROID_STORE_PASSWORD", "AGENT_ANDROID_KEY_PASSWORD")
    .map { providers.environmentVariable(it).orNull }
require(externalSigning.all { it == null } || externalSigning.all { !it.isNullOrBlank() }) {
    "Supply all four Android release signing environment variables"
}

android {
    namespace = "com.agentworkspace.mobile"
    compileSdk = 35
    buildToolsVersion = "35.0.0"
    ndkVersion = "27.3.13750724"

    defaultConfig {
        applicationId = "com.agentworkspace.mobile"
        minSdk = 26
        targetSdk = 35
        versionCode = 10300
        versionName = "1.3.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        // Local test builds can inspect the console page over adb (chrome://inspect) while keeping
        // the release signature; published builds never set AGENT_WEBVIEW_DEBUG.
        // A resource, not a BuildConfig constant: Kotlin inlines constants and incremental builds
        // then keep a stale value.
        resValue("bool", "webview_debug",
            (providers.environmentVariable("AGENT_WEBVIEW_DEBUG").orNull == "1").toString())

        ndk {
            abiFilters += listOf("arm64-v8a", "x86_64")
        }
        externalNativeBuild {
            cmake {
                targets += listOf("agent_qwen", "agent_qwen_dotprod")
                val archive = providers.environmentVariable("AGENT_LLAMA_ARCHIVE").orNull
                    ?: file("build/tooling/llama.cpp-7fe450e19305b828c199d602c23a8337aaa1f03b.tar.gz")
                        .absolutePath
                arguments += "-DAGENT_LLAMA_ARCHIVE=${archive.replace(File.separatorChar, '/')}"
            }
        }
    }

    externalNativeBuild {
        cmake {
            path = file("src/main/cpp/CMakeLists.txt")
            version = "3.22.1"
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        compose = true
    }

    androidResources {
        ignoreAssetsPatterns += listOf(
            "!.svn", "!.git", "!.ds_store", "!*.scc", ".*", "<dir>_*",
            "!CVS", "!thumbs.db", "!picasa.ini", "!*~", "termux-bootstrap-arm64.zip"
        )
    }

    if (externalSigning.all { !it.isNullOrBlank() }) {
        val supplied = signingConfigs.create("externalRelease") {
            storeFile = file(externalSigning[0]!!)
            keyAlias = externalSigning[1]
            storePassword = externalSigning[2]
            keyPassword = externalSigning[3]
        }
        buildTypes.getByName("release").signingConfig = supplied
    }

    packaging {
        jniLibs {
            useLegacyPackaging = true
            keepDebugSymbols += setOf("**/libagent_proot.so", "**/libagent_proot_loader.so",
                "**/libtalloc.so", "**/libandroid-shmem.so")
            pickFirsts += "**/libsqlite3_python.so"
            // The dot-product engine build exists for arm64 only (src/main/cpp/CMakeLists.txt).
            excludes += "lib/x86_64/libagent_qwen_dotprod.so"
        }
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }
}

val embeddedSqlite by configurations.creating {
    isCanBeConsumed = false
    isTransitive = false
}
val prepareEmbeddedSqliteClasses by tasks.registering(Copy::class) {
    from({ zipTree(embeddedSqlite.singleFile) }) {
        include("classes.jar")
    }
    into(layout.buildDirectory.dir("sqlite/classes"))
}
// Chaquopy's SQLite omits FTS5, which the event store needs at startup.
androidComponents.onVariants { variant ->
    val variantTaskName = variant.name.replaceFirstChar { it.uppercaseChar() }
    val prepareVariantSqlite = tasks.register<Copy>("prepare${variantTaskName}EmbeddedSqlite") {
        dependsOn("generate${variantTaskName}PythonJniLibs")
        from({ zipTree(embeddedSqlite.singleFile) }) {
            include("jni/arm64-v8a/libsqliteX.so", "jni/x86_64/libsqliteX.so")
            eachFile {
                relativePath = RelativePath(true, *relativePath.segments.drop(1).toTypedArray())
            }
            rename("libsqliteX.so", "libsqlite3_python.so")
            includeEmptyDirs = false
        }
        into(layout.buildDirectory.dir("python/jniLibs/${variant.name}"))
    }
    tasks.configureEach {
        if (name == "merge${variantTaskName}JniLibFolders") {
            dependsOn(prepareVariantSqlite)
        }
    }
}

val embeddedBuildPython = providers.environmentVariable("AGENT_WORKSPACE_BUILD_PYTHON").orNull

chaquopy {
    defaultConfig {
        version = "3.12"
        embeddedBuildPython?.let { buildPython(it) }
        pip {
            options("--only-binary=:all:")
            install("httpx==0.28.1")
            install("websockets==17.0.1")
            install("pypdf==6.16.1")
            install("tomli-w==1.2.0")
            // This release supports Draft 2020-12 without an unavailable Rust Android wheel.
            install("jsonschema==4.17.3")
            install("pyrsistent==0.20.0")
            install("attrs==25.4.0")
        }
    }
}

val prepareAndroidAssets by tasks.registering(Exec::class) {
    workingDir = file("..")
    val pythonCommand = embeddedBuildPython?.let { listOf(it) }
        ?: if (System.getProperty("os.name").startsWith("Windows")) {
            listOf("py", "-3.12")
        } else {
            listOf("python3")
        }
    commandLine(pythonCommand + listOf(
        file("../package_apk_assets.py").absolutePath, "--runtime", "chaquopy"
    ))
}

val prepareAndroidToolchainLaunchers by tasks.registering(Exec::class) {
    workingDir = file("..")
    val pythonCommand = embeddedBuildPython?.let { listOf(it) }
        ?: if (System.getProperty("os.name").startsWith("Windows")) listOf("py", "-3.12")
        else listOf("python3")
    commandLine(pythonCommand + listOf(file("../prepare_android_toolchain.py").absolutePath))
}

val prepareAndroidNativeSources by tasks.registering(Exec::class) {
    workingDir = file("..")
    val pythonCommand = embeddedBuildPython?.let { listOf(it) }
        ?: if (System.getProperty("os.name").startsWith("Windows")) listOf("py", "-3.12")
        else listOf("python3")
    commandLine(pythonCommand + listOf("-c",
        "from build_release import prepare_native_source, prepare_license_assets; " +
        "prepare_native_source(); prepare_license_assets()"))
}

tasks.configureEach {
    if (name.startsWith("configureCMake") || name.startsWith("buildCMake")) {
        dependsOn(prepareAndroidNativeSources)
    }
}

tasks.named("preBuild") {
    dependsOn(prepareAndroidAssets, prepareAndroidToolchainLaunchers, prepareAndroidNativeSources)
}

dependencies {
    implementation("com.google.mlkit:text-recognition-chinese:16.0.1")
    // 3.50.4+: its native library is 16 KB page aligned (Android 15+ devices with 16 KB pages
    // refuse to load the 4 KB aligned 3.45.2 build, which stopped the engine at start-up).
    embeddedSqlite("mil.nga:sqlite-android:3500400@aar")
    // AndroidPlatform preloads sqlite3_python through ART, which calls the library's JNI_OnLoad.
    implementation(files(layout.buildDirectory.file("sqlite/classes/classes.jar")).builtBy(prepareEmbeddedSqliteClasses))
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.ui)
    implementation(libs.androidx.ui.graphics)
    implementation(libs.androidx.ui.tooling.preview)
    implementation(libs.androidx.material3)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.webkit)
    implementation(libs.kotlinx.coroutines.android)
    implementation("androidx.work:work-runtime-ktx:2.10.1")
    implementation(libs.shizuku.api)
    // Pure-logic tests (memory planning) run on the JVM without a device.
    testImplementation("junit:junit:4.13.2")
    androidTestImplementation("androidx.test.ext:junit:1.2.1")
    androidTestImplementation("androidx.test:runner:1.6.2")
}
