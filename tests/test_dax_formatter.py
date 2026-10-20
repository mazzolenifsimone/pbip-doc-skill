"""Unit tests for pbip_doc.dax_formatter."""
import unittest
from pbip_doc.dax_formatter import format_dax, strip_dax_comments


class TestDaxFormatter(unittest.TestCase):

    def test_strip_comments_line_double_slash(self):
        dax = "// This is a comment\nSUM(Sales[Amount]) // trailing comment"
        stripped = strip_dax_comments(dax)
        self.assertNotIn("//", stripped)
        self.assertIn("SUM(Sales[Amount])", stripped)

    def test_strip_comments_line_double_dash(self):
        dax = "-- Single line dash comment\nCALCULATE([Sales], Dates[Year] = 2024) -- end of line"
        stripped = strip_dax_comments(dax)
        self.assertNotIn("--", stripped)
        self.assertIn("CALCULATE([Sales], Dates[Year] = 2024)", stripped)

    def test_strip_comments_block(self):
        dax = "/* Multi-line\n   comment */\nDIVIDE([A], [B], 0)"
        stripped = strip_dax_comments(dax)
        self.assertNotIn("/*", stripped)
        self.assertNotIn("*/", stripped)
        self.assertIn("DIVIDE([A], [B], 0)", stripped)

    def test_comments_inside_string_literals_preserved(self):
        dax = 'LOOKUPVALUE(Table[Col], Table[Url], "https://example.com/api//test--v1/*keep*/")'
        stripped = strip_dax_comments(dax)
        self.assertIn('"https://example.com/api//test--v1/*keep*/"', stripped)

    def test_comments_inside_bracketed_identifiers_preserved(self):
        dax = "[Sales -- Net] + [Sales // 2024]"
        stripped = strip_dax_comments(dax)
        self.assertEqual(stripped, "[Sales -- Net] + [Sales // 2024]")

    def test_comments_inside_quoted_tables_preserved(self):
        dax = "'Sales // Fact'[Amount] + 'Sales -- Old'[Amount]"
        stripped = strip_dax_comments(dax)
        self.assertEqual(stripped, "'Sales // Fact'[Amount] + 'Sales -- Old'[Amount]")

    def test_measure_signature_prepended(self):
        raw = "sum(Sales[Amount])"
        formatted = format_dax(raw, name="Total Sales", entity_type="measure")
        self.assertTrue(formatted.startswith("[Total Sales] =\n"))
        self.assertIn("SUM ( Sales[Amount] )", formatted)

    def test_measure_already_has_signature_not_duplicated(self):
        raw = "[Total Sales] = sum(Sales[Amount])"
        formatted = format_dax(raw, name="Total Sales", entity_type="measure")
        self.assertEqual(formatted.count("[Total Sales] ="), 1)
        self.assertTrue(formatted.startswith("[Total Sales] =\n"))

    def test_calculated_column_signature(self):
        raw = "upper(Products[Category])"
        formatted = format_dax(
            raw,
            name="Clean Category",
            entity_type="calculated_column",
            table_name="Products",
        )
        self.assertTrue(formatted.startswith("'Products'[Clean Category] =\n"))
        self.assertIn("UPPER ( Products[Category] )", formatted)

    def test_calculated_table_signature(self):
        raw = "calendar(date(2020, 1, 1), date(2025, 12, 31))"
        formatted = format_dax(raw, name="DimDate", entity_type="calculated_table")
        self.assertTrue(formatted.startswith("'DimDate' =\n"))
        self.assertIn("CALENDAR ( DATE ( 2020, 1, 1 ), DATE ( 2025, 12, 31 ) )", formatted)

    def test_function_signature(self):
        raw = "ParamA * ParamC"
        formatted = format_dax(
            raw,
            name="ComplexCalc",
            entity_type="function",
            parameters_signature="(ParamA: double, ParamC: int64): double =>",
        )
        self.assertTrue(formatted.startswith("FUNCTION ComplexCalc = (ParamA: double, ParamC: int64): double =>\n"))
        self.assertIn("ParamA * ParamC", formatted)

    def test_var_return_multiline_formatting(self):
        raw = """// Comment
var _current_year = year(today())
var _sales = calculate([Total Sales], Dates[Year] = _current_year)
return
_sales"""
        formatted = format_dax(raw, name="Current Year Sales", entity_type="measure")
        lines = formatted.splitlines()
        self.assertEqual(lines[0], "[Current Year Sales] =")
        self.assertEqual(lines[1], "VAR _current_year = YEAR ( TODAY () )")
        self.assertIn("VAR _sales = CALCULATE ( [Total Sales], Dates[Year] = _current_year )", lines[2])
        self.assertEqual(lines[3], "RETURN")
        self.assertEqual(lines[4], "    _sales")

    def test_empty_dax_expression(self):
        formatted = format_dax("", name="BlankMeasure", entity_type="measure")
        self.assertEqual(formatted, "[BlankMeasure] =\nBLANK ()")

    def test_operator_spacing_and_capitalization(self):
        raw = "[Cat] in {\"A\", \"B\"} && [Amount]>=100"
        formatted = format_dax(raw, name="Filtered", entity_type="measure")
        self.assertIn("IN { \"A\", \"B\" }", formatted)
        self.assertIn("&& [Amount] >= 100", formatted)

    def test_dynamic_function_detection_without_hardcoded_list(self):
        """Verifies that future/arbitrary DAX functions are capitalized structurally without needing any hardcoded list."""
        raw = "mycustomfunc(some_future_ai_func([Amount], 42), other_func())"
        formatted = format_dax(raw, name="FutureTest", entity_type="measure")
        self.assertIn("MYCUSTOMFUNC ( SOME_FUTURE_AI_FUNC ( [Amount], 42 ), OTHER_FUNC () )", formatted)


if __name__ == "__main__":
    unittest.main()
