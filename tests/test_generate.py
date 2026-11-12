import json, re, shutil, sys, tempfile, unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import generate as g  # noqa: E402


class GenerateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        shutil.copy(REPO / "template.html", self.tmp / "template.html")
        (self.tmp / "ndas.json").write_text("[]")
        self.base = ["--company", "Acme Traders Pvt. Ltd.", "--address", "1 Main Rd, Pune 411001",
                     "--gst", "27AAAAA0000A1Z5", "--signatory", "Jane Roe", "--purpose", "LinkedIn Personal Branding",
                     "--date", "1st January 2027", "--root", str(self.tmp)]

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_key_rules(self):
        self.assertEqual(g.make_key("Alphastar Technologies Private Limited"), "alphastar-technologies")
        self.assertEqual(g.make_key("TechCorp India Pvt. Ltd."), "techcorp-india")
        self.assertEqual(g.make_key("ABC Solutions"), "abc-solutions")
        self.assertEqual(g.make_key("CAUTILYA WEALTH AND EDUCATION PVT LTD."), "cautilya-wealth-and-education")

    def test_collision_gets_numeric_suffix(self):
        g.main(self.base)
        e = g.main(self.base)
        self.assertEqual(e["id"], "acme-traders-2")
        self.assertEqual(g.main(self.base)["id"], "acme-traders-3")

    def test_generates_page_and_registry(self):
        e = g.main(self.base)
        page = (self.tmp / "ndas" / "acme-traders.html").read_text()
        self.assertEqual(e["url"], "https://teamrocketrush-ui.github.io/rr-ndas/ndas/acme-traders.html")
        self.assertNotIn("{{", page)
        self.assertIn("Acme Traders Pvt. Ltd.", page)
        self.assertIn("GST No. 27AAAAA0000A1Z5", page)
        reg = json.loads((self.tmp / "ndas.json").read_text())
        self.assertEqual([r["id"] for r in reg], ["acme-traders"])

    def test_gst_na_is_omitted(self):
        args = [a if a != "27AAAAA0000A1Z5" else "N/A" for a in self.base]
        g.main(args)
        page = (self.tmp / "ndas" / "acme-traders.html").read_text()
        self.assertNotIn("GST No. N/A", page)
        self.assertNotIn("<b>GST</b> N/A", page)

    def test_input_is_escaped_in_html_and_js(self):
        evil = '</script><img src=x onerror=alert(1)> "Q" \'q\''
        args = [a if a != "Jane Roe" else evil for a in self.base]
        g.main(args)
        page = (self.tmp / "ndas" / "acme-traders.html").read_text()
        self.assertNotIn("<img src=x", page)
        self.assertNotIn("</script><img", page)
        m = re.search(r"const CLIENT_SIGNATORY\s*=\s*(.*);", page)
        self.assertEqual(json.loads(m.group(1).replace("\\u003c", "<").replace("\\u003e", ">")), evil)

    def test_private_suffix(self):
        e = g.main(self.base + ["--private-suffix"])
        self.assertRegex(e["id"], r"^acme-traders-[0-9a-f]{4}$")

    def test_missing_required_field(self):
        with self.assertRaises(SystemExit):
            g.main([a if a != "1 Main Rd, Pune 411001" else "  " for a in self.base])

    def test_default_date_and_place(self):
        args = [a for a in self.base]
        i = args.index("--date"); del args[i:i + 2]
        e = g.main(args)
        self.assertEqual(e["exec_place"], "Noida")
        self.assertRegex(e["exec_date"], r"^\d{1,2}(st|nd|rd|th) [A-Z][a-z]+ \d{4}$")

    def test_individual_mode(self):
        args = ["--type", "individual", "--company", "Rajnish Kumar", "--address", "12 Park St, Delhi 110001",
                "--gst", "N/A", "--purpose", "LinkedIn Personal Branding", "--date", "1st January 2027",
                "--root", str(self.tmp)]
        e = g.main(args)
        self.assertEqual((e["id"], e["type"], e["signatory"]), ("rajnish-kumar", "individual", "Rajnish Kumar"))
        page = (self.tmp / "ndas" / "rajnish-kumar.html").read_text()
        self.assertNotIn("<!--IF", page)
        self.assertNotIn("<!--/IF", page)
        self.assertIn("<b>Rajnish Kumar</b>, residing at 12 Park St, Delhi 110001 (", page)
        self.assertIn("natural person of full age and legal capacity", page)
        self.assertNotIn("is a company duly constituted", page)
        self.assertNotIn("Registered Office at 12 Park", page)
        self.assertNotIn("Authorised Signatory — Rajnish Kumar", page)
        self.assertIn('<div class="sig-title-text">Disclosing Party</div>', page)
        self.assertNotIn("GST No. N/A", page)

    def test_individual_without_address(self):
        e = g.main(["--type", "individual", "--company", "Rajnish Kumar", "--purpose", "LinkedIn Personal Branding",
                    "--date", "1st January 2027", "--root", str(self.tmp)])
        self.assertEqual(e["address"], "")
        page = (self.tmp / "ndas" / "rajnish-kumar.html").read_text()
        self.assertNotIn("residing", page)
        self.assertNotIn("{{", page)
        self.assertIn("<b>Rajnish Kumar</b> (“Disclosing Party”)", page)
        self.assertIn('<div class="party-meta">Individual</div>', page)

    def test_company_still_requires_address(self):
        with self.assertRaises(SystemExit):
            g.main(["--company", "Acme Pvt Ltd", "--purpose", "X", "--root", str(self.tmp)])

    def test_company_mode_keeps_original_clause_20(self):
        g.main(self.base)
        page = (self.tmp / "ndas" / "acme-traders.html").read_text()
        self.assertNotIn("<!--IF", page)
        self.assertIn("is a company duly constituted under the laws of their respective countries", page)
        self.assertNotIn("natural person", page)
        self.assertIn("with its Registered Office at 1 Main Rd", page)
        self.assertIn("Authorised Signatory — Acme Traders Pvt. Ltd.", page)

    def test_existing_cautilya_page_matches_current_template(self):
        reg = json.loads((REPO / "ndas.json").read_text())
        c = next(r for r in reg if r["id"] == "cautilya-wealth-and-education")
        g.main(["--company", c["client_name"], "--address", c["address"], "--gst", c["gst"],
                "--signatory", c["signatory"], "--purpose", c["purpose"], "--date", c["exec_date"],
                "--place", c["exec_place"], "--root", str(self.tmp)])
        regenerated = (self.tmp / "ndas" / "cautilya-wealth-and-education.html").read_text()
        committed = (REPO / "ndas" / "cautilya-wealth-and-education.html").read_text()
        self.assertEqual(regenerated, committed)

    def test_ordinals(self):
        self.assertEqual([g.ordinal(n) for n in (1, 2, 3, 4, 11, 12, 13, 21, 22, 23, 31)],
                         ["1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st", "22nd", "23rd", "31st"])

    def test_template_has_25_clauses_in_order(self):
        t = (REPO / "template.html").read_text()
        nums = re.findall(r'<span class="acc-num">(\d\d)</span>', t)
        self.assertEqual(nums, [f"{i:02d}" for i in range(1, 26)])


if __name__ == "__main__":
    unittest.main()
