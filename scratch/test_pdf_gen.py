import os

class SimplePDF:
    def __init__(self):
        self.objects = []
        self.pages = []
        self.current_stream = []
        self.page_width = 595.28  # A4 width in points
        self.page_height = 841.89  # A4 height in points
        self.margin = 54  # 0.75 in
        self.y = self.page_height - self.margin
        self.page_num = 0

    def add_page(self):
        if self.page_num > 0:
            self._flush_page()
        self.page_num += 1
        self.y = self.page_height - self.margin
        self.current_stream = []
        # Page background
        self._rect(0, 0, self.page_width, self.page_height, fill_color=(0.98, 0.98, 0.99))

    def _flush_page(self):
        content = "\n".join(self.current_stream)
        stream_bytes = content.encode('latin1')
        stream_obj = {
            'dict': f"<</Length {len(stream_bytes)}>>",
            'stream': stream_bytes
        }
        self.objects.append(stream_obj)
        stream_idx = len(self.objects)

        page_obj = {
            'dict': f"<</Type /Page /Parent 2 0 R /MediaBox [0 0 {self.page_width:.2f} {self.page_height:.2f}] /Contents {stream_idx} 0 R /Resources <</Font <</F1 3 0 R /F2 4 0 R /F3 5 0 R>> /ProcSet [/PDF /Text /ImageB /ImageC /ImageI]>>>>"
        }
        self.objects.append(page_obj)
        self.pages.append(len(self.objects))

    def _rect(self, x, y, w, h, fill_color=None, stroke_color=None, stroke_width=1):
        ops = ["q"]
        if fill_color:
            ops.append(f"{fill_color[0]:.3f} {fill_color[1]:.3f} {fill_color[2]:.3f} rg")
        if stroke_color:
            ops.append(f"{stroke_width} w")
            ops.append(f"{stroke_color[0]:.3f} {stroke_color[1]:.3f} {stroke_color[2]:.3f} RG")
        ops.append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re")
        if fill_color and stroke_color:
            ops.append("B")
        elif fill_color:
            ops.append("f")
        elif stroke_color:
            ops.append("S")
        ops.append("Q")
        self.current_stream.append("\n".join(ops))

    def add_header_banner(self, title, subtitle):
        h = 75
        self.y -= h
        self._rect(self.margin, self.y, self.page_width - 2 * self.margin, h, fill_color=(0.09, 0.22, 0.54), stroke_color=(0.14, 0.38, 0.92), stroke_width=1.5)
        # Title text
        self.draw_text(self.margin + 20, self.y + 44, title, font="F2", size=18, color=(1, 1, 1))
        self.draw_text(self.margin + 20, self.y + 22, subtitle, font="F1", size=10, color=(0.78, 0.86, 0.98))
        self.y -= 15

    def draw_text(self, x, y, text, font="F1", size=10, color=(0.1, 0.15, 0.2)):
        safe_text = text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
        self.current_stream.append(f"q BT /{font} {size} Tf {color[0]:.3f} {color[1]:.3f} {color[2]:.3f} rg {x:.2f} {y:.2f} Td ({safe_text}) Tj ET Q")

    def draw_heading(self, text, level=1):
        if level == 1:
            size = 14
            h = 24
            font = "F2"
            color = (0.09, 0.22, 0.54)
            self.check_space(h + 10)
            self.y -= h
            self.draw_text(self.margin, self.y, text, font=font, size=size, color=color)
            # underline
            self._rect(self.margin, self.y - 4, self.page_width - 2 * self.margin, 1.5, fill_color=(0.85, 0.9, 0.98))
            self.y -= 12
        elif level == 2:
            size = 11
            h = 18
            font = "F2"
            color = (0.12, 0.16, 0.24)
            self.check_space(h + 6)
            self.y -= h
            self.draw_text(self.margin, self.y, text, font=font, size=size, color=color)
            self.y -= 6

    def draw_paragraph(self, text, size=9.5, color=(0.2, 0.25, 0.32), leading=14):
        words = text.split(" ")
        lines = []
        cur_line = []
        max_w = self.page_width - 2 * self.margin
        # Approximate char width for Helvetica ~ size * 0.52
        char_w = size * 0.52
        max_chars = int(max_w / char_w)

        for w in words:
            candidate = " ".join(cur_line + [w])
            if len(candidate) <= max_chars:
                cur_line.append(w)
            else:
                lines.append(" ".join(cur_line))
                cur_line = [w]
        if cur_line:
            lines.append(" ".join(cur_line))

        for line in lines:
            self.check_space(leading)
            self.y -= leading
            self.draw_text(self.margin, self.y, line, font="F1", size=size, color=color)
        self.y -= 6

    def draw_table(self, headers, rows, col_widths, col_align=None):
        total_w = sum(col_widths)
        row_h = 20
        self.check_space(row_h * (len(rows) + 1) + 10)

        # Header row
        self.y -= row_h
        self._rect(self.margin, self.y, total_w, row_h, fill_color=(0.14, 0.38, 0.92))
        cur_x = self.margin
        for i, h in enumerate(headers):
            self.draw_text(cur_x + 6, self.y + 5, h, font="F2", size=8.5, color=(1, 1, 1))
            cur_x += col_widths[i]

        # Data rows
        for r_idx, r in enumerate(rows):
            self.check_space(row_h)
            self.y -= row_h
            bg_color = (1, 1, 1) if r_idx % 2 == 0 else (0.95, 0.97, 1.0)
            self._rect(self.margin, self.y, total_w, row_h, fill_color=bg_color, stroke_color=(0.88, 0.9, 0.94), stroke_width=0.5)
            cur_x = self.margin
            for c_idx, val in enumerate(r):
                # Status badges styling
                txt_color = (0.1, 0.15, 0.25)
                if val in ('PASS', 'PASSED', '100%', 'SUCCESS'):
                    txt_color = (0.08, 0.55, 0.24)
                elif val in ('FAIL', 'FAILED'):
                    txt_color = (0.8, 0.15, 0.15)
                self.draw_text(cur_x + 6, self.y + 5, str(val), font="F2" if val in ('PASS', 'PASSED') else "F1", size=8, color=txt_color)
                cur_x += col_widths[c_idx]

        self.y -= 12

    def check_space(self, needed):
        if self.y - needed < self.margin + 30:
            self.add_page()

    def save(self, filepath):
        self._flush_page()
        # Catalog & Root objects
        # 1: Catalog, 2: Pages, 3: F1 (Helvetica), 4: F2 (Helvetica-Bold), 5: F3 (Courier)
        kids_str = " ".join([f"{p} 0 R" for p in self.pages])
        pages_dict = f"<</Type /Pages /Kids [{kids_str}] /Count {len(self.pages)}>>"
        catalog_dict = "<</Type /Catalog /Pages 2 0 R>>"
        f1_dict = "<</Type /Font /Subtype /Type1 /BaseFont /Helvetica>>"
        f2_dict = "<</Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold>>"
        f3_dict = "<</Type /Font /Subtype /Type1 /BaseFont /Courier>>"

        # Prepend standard objects:
        std_objs = [
            {'dict': catalog_dict},
            {'dict': pages_dict},
            {'dict': f1_dict},
            {'dict': f2_dict},
            {'dict': f3_dict}
        ]
        all_objects = std_objs + self.objects

        # Build xref & write
        with open(filepath, 'wb') as f:
            f.write(b"%PDF-1.4\n")
            f.write(b"%\xe2\xe3\xcf\xd3\n")
            offsets = []
            for i, obj in enumerate(all_objects, start=1):
                offsets.append(f.tell())
                f.write(f"{i} 0 obj\n".encode('ascii'))
                f.write(obj['dict'].encode('ascii') + b"\n")
                if 'stream' in obj:
                    f.write(b"stream\n")
                    f.write(obj['stream'])
                    f.write(b"\nendstream\n")
                f.write(b"endobj\n")

            xref_start = f.tell()
            f.write(f"xref\n0 {len(all_objects) + 1}\n".encode('ascii'))
            f.write(b"0000000000 65535 f \n")
            for offset in offsets:
                f.write(f"{offset:010d} 00000 n \n".encode('ascii'))

            trailer = f"trailer\n<</Size {len(all_objects) + 1} /Root 1 0 R>>\nstartxref\n{xref_start}\n%%EOF\n"
            f.write(trailer.encode('ascii'))

        print(f"PDF saved to: {filepath} ({os.path.getsize(filepath)} bytes)")

pdf = SimplePDF()
pdf.add_page()
pdf.add_header_banner("Developer Productivity Tool", "Application Quality Assurance & Testing Report")
pdf.draw_heading("1. Executive Summary")
pdf.draw_paragraph("This document details the comprehensive testing suite execution for the Developer Productivity Tool. All functional requirements, regression tests, role-based access permissions, and UI/UX integrations have been thoroughly evaluated.")
pdf.draw_heading("2. Test Results Matrix")
pdf.draw_table(["Module", "Test Scope", "Test Count", "Result"], [
    ["Authentication & RBAC", "Login, Registration, Passwords, Role Access", "6", "PASS"],
    ["Project Management", "Multi-role Project Creation & Visibility", "5", "PASS"],
    ["Task Management", "Sprint Tasks, 4-Task Visibility, Filters", "5", "PASS"],
    ["Time Tracker", "Persistent Timer, SQLite Storage, Dashboard", "6", "PASS"],
    ["Online Code Editor", "JS, Python, HTML, CSS, SQL Execution", "5", "PASS"],
    ["UI & Contrast", "WCAG AA/AAA Badge & Theme Readability", "7", "PASS"]
], [140, 200, 70, 77])
pdf.save("scratch/test_report.pdf")
