import unittest

from mobguard_platform.template_utils import render_optional_template


class TemplateUtilsTests(unittest.TestCase):
    def test_optional_line_is_removed_when_placeholder_is_empty(self):
        template = (
            "Hello {{username}}\n"
            "Review URL: {{review_url}}\n"
            "Bye"
        )
        rendered = render_optional_template(template, {"username": "alice", "review_url": ""}, str)
        self.assertEqual(rendered, "Hello alice\nBye")

    def test_optional_line_is_rendered_when_placeholder_is_present(self):
        template = (
            "Hello {{username}}\n"
            "Review URL: {{review_url}}\n"
            "Bye"
        )
        rendered = render_optional_template(
            template,
            {"username": "alice", "review_url": "https://mobguard.example.com/reviews/1"},
            str,
        )
        self.assertIn("Review URL: https://mobguard.example.com/reviews/1", rendered)


if __name__ == "__main__":
    unittest.main()
