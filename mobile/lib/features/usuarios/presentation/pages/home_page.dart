import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/theme/app_theme.dart';

class HomePage extends StatelessWidget {
	const HomePage({super.key});

	@override
	Widget build(BuildContext context) {
		return Scaffold(
			appBar: AppBar(
				title: const Text('SITUR-SMART'),
				actions: [
					TextButton.icon(
						onPressed: () => context.go('/login'),
						icon: const Icon(Icons.logout, size: 18),
						label: const Text('Salir'),
					),
				],
			),
			body: Center(
				child: Container(
					margin: const EdgeInsets.all(24),
					padding: const EdgeInsets.all(24),
					decoration: BoxDecoration(
						color: AppTheme.inputBg,
						borderRadius: BorderRadius.circular(16),
						border: Border.all(color: AppTheme.inputBorder),
					),
					child: const Column(
						mainAxisSize: MainAxisSize.min,
						children: [
							Icon(Icons.check_circle_outline, color: AppTheme.accentDark, size: 40),
							SizedBox(height: 12),
							Text(
								'Inicio de sesión exitoso',
								style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: AppTheme.titleColor),
							),
							SizedBox(height: 8),
							Text(
								'Pantalla principal temporal lista para conectar con módulos funcionales.',
								textAlign: TextAlign.center,
								style: TextStyle(fontSize: 14, color: AppTheme.textSecondary),
							),
						],
					),
				),
			),
		);
	}
}
