import 'package:flutter/material.dart';

class AppTheme {
	AppTheme._();

	static const Color accent = Color(0xFF2DD4BF);
	static const Color accentDark = Color(0xFF0F766E);
	static const Color accentGradientTo = Color(0xFF22B5A0);
	static const Color panelBg = Color(0xFF0D4F47);
	static const Color titleColor = Color(0xFF111827);
	static const Color textSecondary = Color(0xFF6B7280);
	static const Color labelColor = Color(0xFF374151);
	static const Color inputBg = Color(0xFFF9FAFB);
	static const Color inputBorder = Color(0xFFE5E7EB);
	static const Color errorColor = Color(0xFFEF4444);
	static const Color demoBg = Color(0xFFF0FDFB);
	static const Color demoBorder = Color(0xFF99F6E4);

	static ThemeData get light {
		final colorScheme = ColorScheme.fromSeed(
			seedColor: accent,
			brightness: Brightness.light,
		).copyWith(
			primary: accent,
			secondary: accentGradientTo,
			error: errorColor,
			surface: Colors.white,
			onSurface: titleColor,
		);

		return ThemeData(
			useMaterial3: true,
			colorScheme: colorScheme,
			scaffoldBackgroundColor: Colors.white,
			appBarTheme: const AppBarTheme(
				backgroundColor: Colors.white,
				foregroundColor: titleColor,
				elevation: 0,
			),
			inputDecorationTheme: InputDecorationTheme(
				filled: true,
				fillColor: inputBg,
				contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
				hintStyle: const TextStyle(color: textSecondary, fontWeight: FontWeight.w400),
				border: OutlineInputBorder(
					borderRadius: BorderRadius.circular(14),
					borderSide: const BorderSide(color: inputBorder),
				),
				enabledBorder: OutlineInputBorder(
					borderRadius: BorderRadius.circular(14),
					borderSide: const BorderSide(color: inputBorder),
				),
				focusedBorder: OutlineInputBorder(
					borderRadius: BorderRadius.circular(14),
					borderSide: const BorderSide(color: accent, width: 1.5),
				),
				errorBorder: OutlineInputBorder(
					borderRadius: BorderRadius.circular(14),
					borderSide: const BorderSide(color: errorColor),
				),
				focusedErrorBorder: OutlineInputBorder(
					borderRadius: BorderRadius.circular(14),
					borderSide: const BorderSide(color: errorColor, width: 1.5),
				),
			),
			textTheme: const TextTheme(
				headlineMedium: TextStyle(
					fontSize: 32,
					fontWeight: FontWeight.w800,
					height: 1.15,
					color: titleColor,
				),
				titleLarge: TextStyle(
					fontSize: 20,
					fontWeight: FontWeight.w700,
					color: titleColor,
				),
				bodyLarge: TextStyle(fontSize: 16, color: labelColor),
				bodyMedium: TextStyle(fontSize: 14, color: textSecondary),
			),
			elevatedButtonTheme: ElevatedButtonThemeData(
				style: ElevatedButton.styleFrom(
					minimumSize: const Size.fromHeight(52),
					shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
					foregroundColor: Colors.white,
					textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
					elevation: 0,
					backgroundColor: accent,
				),
			),
		);
	}
}
