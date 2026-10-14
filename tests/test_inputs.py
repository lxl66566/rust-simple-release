import unittest

from rust_simple_release.inputs import get_input, get_input_bool, get_input_list

from .utils import set_env


class GetInputTest(unittest.TestCase):
    def test_strips_name_and_value(self):
        self.addCleanup(set_env("456123", " 1 "))
        assert get_input(" 456123  ") == "1"

    def test_unset_returns_none(self):
        self.addCleanup(set_env("456123", None))
        assert get_input("456123") is None

    def test_empty_returns_none(self):
        self.addCleanup(set_env("456123", ""))
        assert get_input("456123") is None


class GetInputListTest(unittest.TestCase):
    def test_comma_separated(self):
        self.addCleanup(set_env("456123", "a,b,123,456"))
        assert get_input_list("456123") == ["a", "b", "123", "456"]

    def test_newline_separated(self):
        self.addCleanup(set_env("456123", "a\nb\n123\n456"))
        assert get_input_list("456123") == ["a", "b", "123", "456"]

    def test_mixed_separators_and_stripping(self):
        self.addCleanup(set_env("456123", " a\nb\n123,456 "))
        assert get_input_list(" 456123  ") == ["a", "b", "123", "456"]

    def test_unset_returns_empty_list(self):
        self.addCleanup(set_env("456123", None))
        assert get_input_list("456123") == []

    def test_empty_returns_empty_list(self):
        self.addCleanup(set_env("456123", ""))
        assert get_input_list("456123") == []


class GetInputBoolTest(unittest.TestCase):
    def test_unset_returns_default(self):
        self.addCleanup(set_env("456123", None))
        assert get_input_bool("456123") is False
        assert get_input_bool("456123", default=False) is False
        assert get_input_bool("456123", default=True) is True

    def test_empty_returns_default(self):
        self.addCleanup(set_env("456123", ""))
        assert get_input_bool("456123") is False
        assert get_input_bool("456123", default=True) is True

    def test_truthy_values(self):
        for value in ("true", "1", "yes", "TRUE", "Yes", "whatever"):
            with self.subTest(value=value):
                self.addCleanup(set_env("456123", value))
                assert get_input_bool("456123") is True

    def test_falsy_values(self):
        for value in ("false", "0", "no", "FALSE", "No"):
            with self.subTest(value=value):
                self.addCleanup(set_env("456123", value))
                assert get_input_bool("456123") is False
