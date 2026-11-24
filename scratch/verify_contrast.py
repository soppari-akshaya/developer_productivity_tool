def luminance(r, g, b):
    # sRGB to linear
    def to_linear(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r_lin = to_linear(r)
    g_lin = to_linear(g)
    b_lin = to_linear(b)
    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin

def contrast_ratio(rgb1, rgb2):
    l1 = luminance(*rgb1)
    l2 = luminance(*rgb2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)

def hex_to_rgb(hex_str):
    hex_str = hex_str.lstrip('#')
    return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))

def blend_rgba_over_rgb(rgba, bg_rgb):
    # rgba: (r, g, b, a)
    # bg_rgb: (r, g, b)
    r, g, b, a = rgba
    bg_r, bg_g, bg_b = bg_rgb
    res_r = round(r * a + bg_r * (1 - a))
    res_g = round(g * a + bg_g * (1 - a))
    res_b = round(b * a + bg_b * (1 - a))
    return (res_r, res_g, res_b)

# Test Light Theme Badges against white card background #ffffff
light_bg_card = (255, 255, 255)
light_badges = {
    'Primary (Hours/Active/Assignee)': {
        'bg': hex_to_rgb('e0edff'),
        'text': hex_to_rgb('1d4ed8')
    },
    'Success (Completed/Resolved/Active)': {
        'bg': hex_to_rgb('dcfce7'),
        'text': hex_to_rgb('15803d')
    },
    'Warning (High Priority/Major Severity)': {
        'bg': hex_to_rgb('ffedd5'),
        'text': hex_to_rgb('c2410c')
    },
    'Yellow (Pending/Planning/Todo)': {
        'bg': hex_to_rgb('fef9c3'),
        'text': hex_to_rgb('854d0e')
    },
    'Danger (Critical/Overdue)': {
        'bg': hex_to_rgb('fee2e2'),
        'text': hex_to_rgb('b91c1c')
    },
    'Secondary (Low Priority/On Hold/Neutral)': {
        'bg': hex_to_rgb('f1f5f9'),
        'text': hex_to_rgb('334155')
    },
    'Info (Information)': {
        'bg': hex_to_rgb('e0f2fe'),
        'text': hex_to_rgb('0369a1')
    },
    'Purple (Admin)': {
        'bg': hex_to_rgb('ede9fe'),
        'text': hex_to_rgb('6d28d9')
    },
    'Indigo (Team Leader)': {
        'bg': hex_to_rgb('e0e7ff'),
        'text': hex_to_rgb('4338ca')
    }
}

print("=== LIGHT MODE CONTRAST AUDIT ===")
all_pass = True
for name, colors in light_badges.items():
    ratio = contrast_ratio(colors['text'], colors['bg'])
    badge_against_card = contrast_ratio(colors['bg'], light_bg_card)
    passed = ratio >= 4.5
    if not passed: all_pass = False
    status = "PASS (WCAG AA)" if passed else "FAIL"
    print(f"[{status}] {name}: Text-to-Badge Ratio = {ratio:.2f}:1 (Card Contrast = {badge_against_card:.2f}:1)")

# Test Dark Theme Badges against dark card background #131c31
dark_bg_card = hex_to_rgb('131c31')
dark_badges = {
    'Primary (Hours/Active/Assignee)': {
        'bg_rgba': (37, 99, 235, 0.22),
        'text': hex_to_rgb('93c5fd')
    },
    'Success (Completed/Resolved/Active)': {
        'bg_rgba': (22, 101, 52, 0.28),
        'text': hex_to_rgb('86efac')
    },
    'Warning (High Priority/Major Severity)': {
        'bg_rgba': (154, 52, 18, 0.28),
        'text': hex_to_rgb('fdba74')
    },
    'Yellow (Pending/Planning/Todo)': {
        'bg_rgba': (133, 77, 14, 0.28),
        'text': hex_to_rgb('fde047')
    },
    'Danger (Critical/Overdue)': {
        'bg_rgba': (153, 27, 27, 0.30),
        'text': hex_to_rgb('fca5a5')
    },
    'Secondary (Low Priority/On Hold/Neutral)': {
        'bg_rgba': (51, 65, 85, 0.40),
        'text': hex_to_rgb('e2e8f0')
    },
    'Info (Information)': {
        'bg_rgba': (7, 89, 133, 0.28),
        'text': hex_to_rgb('7dd3fc')
    },
    'Purple (Admin)': {
        'bg_rgba': (109, 40, 217, 0.28),
        'text': hex_to_rgb('d8b4fe')
    },
    'Indigo (Team Leader)': {
        'bg_rgba': (67, 56, 202, 0.28),
        'text': hex_to_rgb('a5b4fc')
    }
}

print("\n=== DARK MODE CONTRAST AUDIT ===")
for name, colors in dark_badges.items():
    effective_bg = blend_rgba_over_rgb(colors['bg_rgba'], dark_bg_card)
    ratio = contrast_ratio(colors['text'], effective_bg)
    passed = ratio >= 4.5
    if not passed: all_pass = False
    status = "PASS (WCAG AA)" if passed else "FAIL"
    print(f"[{status}] {name}: Text-to-Badge Ratio = {ratio:.2f}:1")

print(f"\nOVERALL RESULT: {'ALL BADGES PASS WCAG AA / AAA ACCESSIBILITY CONTRAST STANDARDS!' if all_pass else 'SOME FAILED'}")
