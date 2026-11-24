import re
from app import create_app

app = create_app()

def test_login_password_eye():
    with app.test_client() as client:
        res = client.get('/login')
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        html = res.data.decode('utf-8')

        # Check suppression rules
        assert '::-ms-reveal' in html, "Missing ::-ms-reveal rule in login HTML"
        assert '::-ms-clear' in html, "Missing ::-ms-clear rule in login HTML"

        # Find the password section
        # Look for password input and surrounding wrapper
        pattern = re.compile(r'<div class="input-icon-wrapper">\s*<i class="fa-solid fa-lock prefix-icon"></i>\s*<input type="password" id="password"[^>]*>.*?(?=</div>\s*</div>)', re.DOTALL)
        match = pattern.search(html)
        assert match, "Password wrapper block not matched"
        block = match.group(0)

        # Count toggle buttons and eye icons in the password block
        toggle_buttons = re.findall(r'id="toggle-password-btn"', block)
        eye_icons = re.findall(r'fa-solid fa-eye', block)

        print(f"Toggle buttons found in password field: {len(toggle_buttons)}")
        print(f"Eye icons found in password field: {len(eye_icons)}")

        assert len(toggle_buttons) == 1, f"Expected exactly 1 toggle button, found {len(toggle_buttons)}"
        assert len(eye_icons) == 1, f"Expected exactly 1 eye icon, found {len(eye_icons)}"
        print("LOGIN PAGE PASSWORD EYE ICON TEST PASSED SUCCESSFULLY!")

if __name__ == '__main__':
    test_login_password_eye()
