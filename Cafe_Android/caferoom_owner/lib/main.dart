import 'package:flutter/material.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/services.dart';

import 'dart:async';

import 'theme/app_theme.dart';
import 'services/AppFirebaseService.dart' as my_custom_service;
import 'services/alerts_service.dart';
import 'services/update_service.dart';
import 'widgets/pdf_report_button.dart';
import 'screens/dashboard_screen.dart';
import 'screens/inventory_screen.dart';
import 'screens/receipts_screen.dart';
import 'screens/other_screens.dart';
import 'screens/financial_analytics_screen.dart';
import 'screens/inventory_intelligence_screen.dart';
import 'screens/customer_insights_screen.dart';
import 'screens/flexible_firestore_screen.dart';
import 'screens/mobile_entry_screen.dart';
import 'screens/request_history_screen.dart';

// Global flag to track Firebase availability
bool firebaseAvailable = false;
const String ownerEmail = 'azzam2332@gamil.com';
const String ownerUid = 'QlDElYYlYTP2AqvcpHoHc74cG162';
const String ownerPassword = '123321123321';

// background message handler (must be top-level)
@pragma('vm:entry-point')
Future<void> _bgMessageHandler(RemoteMessage message) async {
  await Firebase.initializeApp();
}

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // force portrait
  await SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
    DeviceOrientation.portraitDown,
  ]);

  // Initialize Firebase with error handling
  try {
    await Firebase.initializeApp();
    FirebaseFirestore.instance.settings =
        const Settings(persistenceEnabled: true);
    FirebaseMessaging.onBackgroundMessage(_bgMessageHandler);
    firebaseAvailable = true;
    my_custom_service.FirebaseService.setDemoMode(false);
    debugPrint('[Firebase] Connected successfully');
  } catch (e) {
    // Enable demo mode if Firebase fails
    debugPrint('[Firebase] Initialization failed: $e');
    debugPrint('[Firebase] Using demo mode');
    firebaseAvailable = false;
    my_custom_service.FirebaseService.setDemoMode(true);
  }

  runApp(const CafeRoomApp());
}

class CafeRoomApp extends StatelessWidget {
  const CafeRoomApp({super.key});

  @override
  Widget build(BuildContext context) => MaterialApp(
        title: 'CafeRoom',
        debugShowCheckedModeBanner: false,
        theme: AppTheme.dark,
        home: const SplashScreen(),
      );
}

// Splash screen to handle initialization
class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen> {
  Timer? _navigationTimer;

  @override
  void initState() {
    super.initState();
    _navigateToHome();
  }

  void _navigateToHome() {
    _navigationTimer = Timer(const Duration(seconds: 2), () {
      if (!mounted) return;
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: (_) => const AuthGate()),
      );
    });
  }

  @override
  void dispose() {
    _navigationTimer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.bg,
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.local_cafe, color: AppTheme.primary, size: 76),
            const SizedBox(height: 16),
            const Text('CafeRoom',
                style: TextStyle(
                  fontSize: 32,
                  fontWeight: FontWeight.bold,
                  color: AppTheme.primary,
                )),
            const SizedBox(height: 8),
            const Text('Owner Dashboard',
                style: TextStyle(
                  fontSize: 16,
                  color: AppTheme.textMuted,
                )),
            const SizedBox(height: 32),
            const CircularProgressIndicator(color: AppTheme.primary),
            const SizedBox(height: 24),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              decoration: BoxDecoration(
                color: firebaseAvailable
                    ? AppTheme.primary.withValues(alpha: 0.1)
                    : AppTheme.warning.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(
                  color: firebaseAvailable
                      ? AppTheme.primary.withValues(alpha: 0.3)
                      : AppTheme.warning.withValues(alpha: 0.3),
                ),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(
                    firebaseAvailable ? Icons.cloud_done : Icons.cloud_off,
                    color:
                        firebaseAvailable ? AppTheme.primary : AppTheme.warning,
                    size: 20,
                  ),
                  const SizedBox(width: 8),
                  Text(
                    firebaseAvailable ? 'Connected to Firebase' : 'Demo mode',
                    style: TextStyle(
                      color: firebaseAvailable
                          ? AppTheme.primary
                          : AppTheme.warning,
                      fontWeight: FontWeight.bold,
                      fontSize: 13,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class AuthGate extends StatelessWidget {
  const AuthGate({super.key});

  @override
  Widget build(BuildContext context) {
    if (!firebaseAvailable) return const MainShell();

    return StreamBuilder<User?>(
      stream: FirebaseAuth.instance.authStateChanges(),
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Scaffold(
            body: Center(
                child: CircularProgressIndicator(color: AppTheme.primary)),
          );
        }

        final user = snapshot.data;
        if (user == null) return const OwnerLoginScreen();
        if (user.uid != ownerUid) return AccessDeniedScreen(user: user);
        return const MainShell();
      },
    );
  }
}

class OwnerLoginScreen extends StatefulWidget {
  const OwnerLoginScreen({super.key});

  @override
  State<OwnerLoginScreen> createState() => _OwnerLoginScreenState();
}

class _OwnerLoginScreenState extends State<OwnerLoginScreen> {
  final _emailController = TextEditingController(text: ownerEmail);
  final _passwordController = TextEditingController(text: ownerPassword);
  bool _loading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _login();
    });
  }

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _login() async {
    final email = _emailController.text.trim();
    final password = _passwordController.text;
    if (email.isEmpty || password.isEmpty) {
      setState(() => _error = 'Enter email and password');
      return;
    }

    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final credential = await FirebaseAuth.instance.signInWithEmailAndPassword(
        email: email,
        password: password,
      );

      if (credential.user?.uid != ownerUid) {
        await FirebaseAuth.instance.signOut();
        setState(
            () => _error = 'This account is not allowed to access CafeRoom.');
      }
    } on FirebaseAuthException catch (e) {
      setState(() => _error = _authMessage(e));
    } catch (e) {
      setState(() => _error = 'Login failed: $e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  String _authMessage(FirebaseAuthException e) {
    switch (e.code) {
      case 'invalid-email':
        return 'Invalid email address.';
      case 'user-not-found':
      case 'wrong-password':
      case 'invalid-credential':
        return 'Wrong email or password.';
      case 'network-request-failed':
        return 'Network error. Check internet connection.';
      default:
        return e.message ?? 'Login failed.';
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.bg,
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Container(
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  color: AppTheme.surface,
                  borderRadius: BorderRadius.circular(18),
                  border: Border.all(color: AppTheme.surface2),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const Icon(Icons.lock_outline,
                        color: AppTheme.primary, size: 44),
                    const SizedBox(height: 12),
                    const Text(
                      'CafeRoom Owner Login',
                      textAlign: TextAlign.center,
                      style:
                          TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
                    ),
                    const SizedBox(height: 8),
                    const Text(
                      'Signing in with the owner account.',
                      textAlign: TextAlign.center,
                      style: TextStyle(color: AppTheme.textMuted),
                    ),
                    if (_error != null) ...[
                      const SizedBox(height: 24),
                      Text(_error!,
                          style: const TextStyle(color: AppTheme.danger)),
                    ],
                    const SizedBox(height: 20),
                    ElevatedButton.icon(
                      onPressed: _loading ? null : _login,
                      icon: _loading
                          ? const SizedBox(
                              width: 18,
                              height: 18,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Icon(Icons.login),
                      label: Text(_loading ? 'Signing in...' : 'Retry Sign In'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppTheme.primary,
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(vertical: 14),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class AccessDeniedScreen extends StatelessWidget {
  final User user;
  const AccessDeniedScreen({super.key, required this.user});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.bg,
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.block, color: AppTheme.danger, size: 56),
              const SizedBox(height: 16),
              const Text(
                'Access denied',
                style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 8),
              Text(
                '${user.email ?? user.uid} is not the configured owner account.',
                textAlign: TextAlign.center,
                style: const TextStyle(color: AppTheme.textMuted),
              ),
              const SizedBox(height: 20),
              ElevatedButton(
                onPressed: () => FirebaseAuth.instance.signOut(),
                child: const Text('Sign out'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// =====================================================
// MAIN SHELL - bottom nav
// =====================================================
class MainShell extends StatefulWidget {
  const MainShell({super.key});
  @override
  State<MainShell> createState() => _MainShellState();
}

class _MainShellState extends State<MainShell> with WidgetsBindingObserver {
  int _idx = 0;
  List<Map<String, dynamic>> _alerts = [];
  final List<Map<String, dynamic>> _shownAlerts = [];
  bool _checkingForUpdate = false;
  final UpdateInstallCoordinator _updateInstallCoordinator =
      UpdateInstallCoordinator();

  final _screens = const [
    DashboardScreen(),
    InventoryScreen(),
    ReceiptsScreen(),
    DebtsScreen(),
    WasteScreen(),
    AnalyticsScreen(),
    FinancialAnalyticsScreen(),
    InventoryIntelligenceScreen(),
    CustomerInsightsScreen(),
    FlexibleFirestoreScreen(),
    MobileEntryScreen(),
    RequestHistoryScreen(),
  ];

  final _labels = const [
    'Dashboard',
    'Inventory',
    'Receipts',
    'Debts',
    'Waste',
    'Stats',
    'Finance',
    'Smart Stock',
    'Customers',
    'Data',
    'Entry',
    'حالة الطلبات',
  ];

  final _icons = const [
    Icons.dashboard_rounded,
    Icons.inventory_2_rounded,
    Icons.receipt_long_rounded,
    Icons.credit_card_rounded,
    Icons.delete_outline_rounded,
    Icons.bar_chart_rounded,
    Icons.account_balance_wallet_rounded,
    Icons.psychology_rounded,
    Icons.people_rounded,
    Icons.device_hub_rounded,
    Icons.add_circle_outline_rounded,
    Icons.sync_alt_rounded,
  ];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _setupNotifications();
    _loadAlerts();
    Future.delayed(const Duration(seconds: 4), () {
      if (mounted) _checkForAppUpdate(silent: true);
    });
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed &&
        _updateInstallCoordinator.pendingApkPath != null) {
      _resumePendingUpdateInstall();
    }
  }

  Future<void> _resumePendingUpdateInstall() async {
    try {
      final result = await _updateInstallCoordinator.resumePendingInstall();
      if (!mounted || result == null || result == 'permission_required') return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('تم فتح مثبت تحديث Android')),
      );
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('تعذر متابعة تثبيت التحديث: $error')),
        );
      }
    }
  }

  Future<void> _checkForAppUpdate({bool silent = false}) async {
    if (_checkingForUpdate) return;
    setState(() => _checkingForUpdate = true);

    try {
      final update = await MobileUpdateService.checkForUpdate();
      if (!mounted) return;

      if (update == null) {
        if (!silent) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('App is already up to date')),
          );
        }
        return;
      }

      final install = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          backgroundColor: AppTheme.surface,
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          title: const Text('Update Available'),
          content: Text(
            'Version ${update.version} is available. Download and install it now?',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Later'),
            ),
            TextButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Install'),
            ),
          ],
        ),
      );

      if (install != true || !mounted) return;
      await _downloadAndInstallUpdate(update);
    } catch (e) {
      if (!silent && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Update check failed: $e')),
        );
      }
    } finally {
      if (mounted) setState(() => _checkingForUpdate = false);
    }
  }

  Future<void> _downloadAndInstallUpdate(MobileUpdateInfo update) async {
    var progress = 0.0;
    var progressText = 'Starting download...';

    showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) {
          _updateDownloadDialog = (received, total) {
            setDialogState(() {
              if (total > 0) {
                progress = received / total;
                progressText =
                    '${(progress * 100).clamp(0, 100).toStringAsFixed(0)}%';
              } else {
                progress = 0;
                progressText =
                    '${(received / (1024 * 1024)).toStringAsFixed(1)} MB';
              }
            });
          };

          return AlertDialog(
            backgroundColor: AppTheme.surface,
            shape:
                RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
            title: const Text('Downloading Update'),
            content: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                LinearProgressIndicator(
                  value: progress > 0 ? progress : null,
                  color: AppTheme.primary,
                ),
                const SizedBox(height: 12),
                Text(progressText),
              ],
            ),
          );
        },
      ),
    );

    try {
      final apkPath = await MobileUpdateService.downloadApk(
        update,
        onProgress: (received, total) {
          _updateDownloadDialog?.call(received, total);
        },
      );
      _updateDownloadDialog = null;

      if (mounted) Navigator.of(context, rootNavigator: true).pop();
      final result = await _updateInstallCoordinator.install(apkPath);

      if (!mounted) return;
      final message = result == 'permission_required'
          ? 'اسمح بتثبيت التطبيقات من هذا المصدر، وسيُستكمل التحديث تلقائياً عند الرجوع'
          : 'تم فتح مثبت تحديث Android';
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(message)));
    } catch (e) {
      _updateDownloadDialog = null;
      if (mounted) {
        Navigator.of(context, rootNavigator: true).pop();
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Update install failed: $e')),
        );
      }
    }
  }

  void Function(int received, int total)? _updateDownloadDialog;

  Future<void> _loadAlerts() async {
    try {
      // Load alerts from dashboard stream
      my_custom_service.FirebaseService.dashboardStream().listen((snapshot) {
        if (snapshot.exists) {
          final data = my_custom_service.FirebaseService.docData(snapshot);
          final allAlerts = AlertsService.generateAllAlerts(data);

          // Filter alerts that should be shown
          final newAlerts = allAlerts
              .where(
                  (alert) => AlertsService.shouldShowAlert(alert, _shownAlerts))
              .toList();

          if (mounted) {
            setState(() {
              _alerts = newAlerts;
            });
          }
        }
      }, onError: (error) {
        debugPrint('Error loading alerts: $error');
      });
    } catch (e) {
      debugPrint('Error in _loadAlerts: $e');
    }
  }

  Future<void> _setupNotifications() async {
    try {
      await my_custom_service.FirebaseService.setupNotifications();

      // foreground notifications
      FirebaseMessaging.onMessage.listen((msg) {
        final notif = msg.notification;
        if (notif != null && mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Row(children: [
                const Icon(Icons.notifications, color: AppTheme.primary),
                const SizedBox(width: 10),
                Expanded(
                    child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(notif.title ?? '',
                        style: const TextStyle(fontWeight: FontWeight.bold)),
                    if (notif.body != null)
                      Text(notif.body!, style: const TextStyle(fontSize: 12)),
                  ],
                )),
              ]),
              backgroundColor: AppTheme.surface,
              duration: const Duration(seconds: 4),
              behavior: SnackBarBehavior.floating,
              shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12)),
            ),
          );
        }
      });
    } catch (e) {
      debugPrint('Error setting up notifications: $e');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.local_cafe, size: 20),
            const SizedBox(width: 8),
            Text(_labels[_idx],
                style:
                    const TextStyle(fontWeight: FontWeight.bold, fontSize: 18)),
          ],
        ),
        actions: [
          PdfReportButton(screenIndex: _idx),
          if (firebaseAvailable)
            IconButton(
              onPressed: () => FirebaseAuth.instance.signOut(),
              icon: const Icon(Icons.logout),
              tooltip: 'Sign out',
            ),
          IconButton(
            onPressed: _checkingForUpdate
                ? null
                : () => _checkForAppUpdate(silent: false),
            icon: _checkingForUpdate
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.system_update_alt),
            tooltip: 'Check for update',
          ),
          // alerts indicator
          if (_alerts.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(right: 8),
              child: GestureDetector(
                onTap: () => _showAlertsDialog(),
                child: Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: AppTheme.danger.withValues(alpha: 0.2),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(
                        color: AppTheme.danger.withValues(alpha: 0.5)),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.notifications_active,
                          size: 16, color: AppTheme.danger),
                      const SizedBox(width: 4),
                      Text('${_alerts.length}',
                          style: TextStyle(
                              color: AppTheme.danger,
                              fontSize: 12,
                              fontWeight: FontWeight.bold)),
                    ],
                  ),
                ),
              ),
            ),
          // حالة اتصال الكمبيوتر بالمزامنة
          Padding(
            padding: const EdgeInsets.only(right: 16),
            child: StreamBuilder<Map<String, dynamic>>(
              stream: my_custom_service.FirebaseService.syncHealthStream(),
              builder: (_, snap) {
                if (snap.hasError) {
                  return Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(Icons.circle, size: 8, color: AppTheme.danger),
                      const SizedBox(width: 4),
                      const Text('غير متصل',
                          style:
                              TextStyle(color: AppTheme.danger, fontSize: 12)),
                    ],
                  );
                }
                final data = snap.data ?? const <String, dynamic>{};
                final lastSeen =
                    DateTime.tryParse(data['last_seen']?.toString() ?? '');
                final connected = lastSeen != null &&
                    DateTime.now().difference(lastSeen).inMinutes < 2 &&
                    data['status'] != 'error';
                return Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.circle,
                        size: 8,
                        color: connected ? AppTheme.primary : AppTheme.warning),
                    const SizedBox(width: 4),
                    Text(connected ? 'متصل' : 'بانتظار الكمبيوتر',
                        style: TextStyle(
                          color:
                              connected ? AppTheme.primary : AppTheme.warning,
                          fontSize: 12,
                        )),
                  ],
                );
              },
            ),
          ),
        ],
      ),
      body: Column(
        children: [
          // Demo mode banner
          if (!firebaseAvailable)
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: AppTheme.warning.withValues(alpha: 0.1),
                border: Border(
                    bottom: BorderSide(
                        color: AppTheme.warning.withValues(alpha: 0.3))),
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.info_outline, color: AppTheme.warning, size: 16),
                  const SizedBox(width: 8),
                  const Text('Demo mode - sample data for testing',
                      style: TextStyle(
                        color: AppTheme.warning,
                        fontSize: 12,
                        fontWeight: FontWeight.bold,
                      )),
                ],
              ),
            ),
          // Alerts banner
          if (_alerts.isNotEmpty) _buildAlertsBanner(),
          // Main content
          Expanded(
            child: IndexedStack(
              index: _idx,
              children: _screens,
            ),
          ),
        ],
      ),
      bottomNavigationBar: SafeArea(
        top: false,
        child: Container(
          height: 92,
          decoration: BoxDecoration(
            color: AppTheme.surface,
            border: Border(top: BorderSide(color: AppTheme.surface2)),
          ),
          child: ListView.separated(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
            scrollDirection: Axis.horizontal,
            itemCount: _screens.length,
            separatorBuilder: (_, __) => const SizedBox(width: 10),
            itemBuilder: (context, i) => _buildNavItem(i),
          ),
        ),
      ),
    );
  }

  Widget _buildNavItem(int index) {
    final selected = _idx == index;

    return InkWell(
      borderRadius: BorderRadius.circular(16),
      onTap: () => setState(() => _idx = index),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 180),
        curve: Curves.easeOut,
        width: 96,
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 10),
        decoration: BoxDecoration(
          color:
              selected ? AppTheme.primary.withValues(alpha: 0.16) : AppTheme.bg,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: selected
                ? AppTheme.primary.withValues(alpha: 0.35)
                : AppTheme.surface2,
          ),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              _icons[index],
              color: selected ? AppTheme.primary : AppTheme.textMuted,
              size: 22,
            ),
            const SizedBox(height: 6),
            Text(
              _labels[index],
              textAlign: TextAlign.center,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                color: selected ? AppTheme.primary : AppTheme.textMuted,
                fontSize: 11,
                fontWeight: selected ? FontWeight.bold : FontWeight.w500,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildAlertsBanner() {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            AppTheme.danger.withValues(alpha: 0.2),
            AppTheme.warning.withValues(alpha: 0.1)
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        border: Border(
            bottom: BorderSide(color: AppTheme.danger.withValues(alpha: 0.3))),
      ),
      child: Row(
        children: [
          Icon(Icons.warning_amber, color: AppTheme.danger, size: 20),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              'You have ${_alerts.length} new alerts',
              style: const TextStyle(
                color: AppTheme.danger,
                fontWeight: FontWeight.bold,
                fontSize: 13,
              ),
            ),
          ),
          GestureDetector(
            onTap: () => _showAlertsDialog(),
            child: const Text('View all',
                style: TextStyle(
                  color: AppTheme.primary,
                  fontSize: 12,
                  fontWeight: FontWeight.bold,
                )),
          ),
          const SizedBox(width: 4),
          GestureDetector(
            onTap: () {
              setState(() {
                for (final alert in _alerts) {
                  AlertsService.markAlertAsShown(alert, _shownAlerts);
                }
                _alerts = [];
              });
            },
            child: const Text('Dismiss all',
                style: TextStyle(
                  color: AppTheme.textMuted,
                  fontSize: 12,
                )),
          ),
        ],
      ),
    );
  }

  void _showAlertsDialog() {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppTheme.surface,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: Row(
          children: [
            Icon(Icons.notifications_active, color: AppTheme.danger),
            const SizedBox(width: 8),
            const Text('Alerts'),
          ],
        ),
        content: SizedBox(
          width: double.maxFinite,
          child: ListView.builder(
            shrinkWrap: true,
            itemCount: _alerts.length,
            itemBuilder: (context, index) {
              final alert = _alerts[index];
              return _buildAlertCard(alert);
            },
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }

  Widget _buildAlertCard(Map<String, dynamic> alert) {
    final priority = alert['priority'] as String? ?? 'low';
    final title = alert['title'] as String? ?? '';
    final message = alert['message'] as String? ?? '';
    final recommendation = alert['recommendation'] as String? ?? '';

    Color priorityColor;
    switch (priority) {
      case 'critical':
        priorityColor = AppTheme.danger;
        break;
      case 'high':
        priorityColor = AppTheme.warning;
        break;
      case 'medium':
        priorityColor = AppTheme.accent;
        break;
      default:
        priorityColor = AppTheme.textMuted;
    }

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: priorityColor.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: priorityColor.withValues(alpha: 0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: priorityColor.withValues(alpha: 0.2),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(priority,
                    style: TextStyle(
                      color: priorityColor,
                      fontSize: 10,
                      fontWeight: FontWeight.bold,
                    )),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(title,
                    style: const TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 14,
                    )),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(message,
              style: const TextStyle(fontSize: 12, color: AppTheme.textMuted)),
          if (recommendation.isNotEmpty) ...[
            const SizedBox(height: 6),
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: AppTheme.surface2,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                children: [
                  Icon(Icons.lightbulb_outline,
                      size: 14, color: AppTheme.accent),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(recommendation,
                        style: const TextStyle(
                          fontSize: 11,
                          color: AppTheme.textMuted,
                        )),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}
