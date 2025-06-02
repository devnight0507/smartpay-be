from unittest.mock import Mock

from fastapi import Request

from app.api.i18n import (
    TRANSLATIONS,
    SupportedLanguage,
    get_preferred_language,
    get_translated_message,
)


class TestSupportedLanguage:
    """Test cases for SupportedLanguage enum."""

    def test_supported_language_values(self):
        """Test that all supported languages have correct values."""
        assert SupportedLanguage.ENGLISH == "en"
        assert SupportedLanguage.ARABIC == "ar"
        assert SupportedLanguage.FRENCH == "fr"
        assert SupportedLanguage.SPANISH == "es"
        assert SupportedLanguage.GERMAN == "de"

    def test_get_default(self):
        """Test that default language is English."""
        assert SupportedLanguage.get_default() == SupportedLanguage.ENGLISH


class TestGetPreferredLanguage:
    """Test cases for get_preferred_language function."""

    def create_mock_request(self, accept_language: str = "") -> Request:
        """Create a mock request with Accept-Language header."""
        request = Mock(spec=Request)
        request.headers = {"Accept-Language": accept_language} if accept_language else {}
        return request

    def test_get_preferred_language_exact_match(self):
        """Test exact language match."""
        request = self.create_mock_request("fr")
        result = get_preferred_language(request)
        assert result == SupportedLanguage.FRENCH

    def test_get_preferred_language_partial_match(self):
        """Test partial language match (e.g., en-US matches en)."""
        request = self.create_mock_request("en-US")
        result = get_preferred_language(request)
        assert result == SupportedLanguage.ENGLISH

    def test_get_preferred_language_multiple_languages_first_supported(self):
        """Test multiple languages with first supported language returned."""
        request = self.create_mock_request("fr,en,de")
        result = get_preferred_language(request)
        assert result == SupportedLanguage.FRENCH

    def test_get_preferred_language_multiple_languages_skip_unsupported(self):
        """Test multiple languages skipping unsupported ones."""
        request = self.create_mock_request("zh,ja,es,ko")
        result = get_preferred_language(request)
        assert result == SupportedLanguage.SPANISH

    def test_get_preferred_language_with_quality_values(self):
        """Test language with quality values (q=0.9)."""
        request = self.create_mock_request("en;q=0.9,fr;q=0.8")
        result = get_preferred_language(request)
        assert result == SupportedLanguage.ENGLISH

    def test_get_preferred_language_partial_match_with_country(self):
        """Test partial match with country code."""
        request = self.create_mock_request("de-DE,fr-FR")
        result = get_preferred_language(request)
        assert result == SupportedLanguage.GERMAN

    def test_get_preferred_language_no_header(self):
        """Test when no Accept-Language header is present."""
        request = Mock(spec=Request)
        request.headers = {}
        result = get_preferred_language(request)
        assert result == SupportedLanguage.ENGLISH

    def test_get_preferred_language_empty_header(self):
        """Test when Accept-Language header is empty."""
        request = self.create_mock_request("")
        result = get_preferred_language(request)
        assert result == SupportedLanguage.ENGLISH

    def test_get_preferred_language_unsupported_language(self):
        """Test when only unsupported languages are provided."""
        request = self.create_mock_request("zh,ja,ko")
        result = get_preferred_language(request)
        assert result == SupportedLanguage.ENGLISH

    def test_get_preferred_language_unsupported_partial_match(self):
        """Test when partial match is also unsupported."""
        request = self.create_mock_request("zh-CN,ja-JP")
        result = get_preferred_language(request)
        assert result == SupportedLanguage.ENGLISH

    def test_get_preferred_language_complex_header(self):
        """Test complex Accept-Language header with spaces and quality values."""
        request = self.create_mock_request("zh-CN, en;q=0.9, fr;q=0.8, de;q=0.7, *;q=0.5")
        result = get_preferred_language(request)
        assert result == SupportedLanguage.ENGLISH


class TestGetTranslatedMessage:
    """Test cases for get_translated_message function."""

    def test_get_translated_message_default_english(self):
        """Test getting message in default English language."""
        result = get_translated_message("OperationSuccessful")
        assert result == "The operation was successful."

    def test_get_translated_message_specific_language(self):
        """Test getting message in specific language."""
        result = get_translated_message("OperationSuccessful", language=SupportedLanguage.FRENCH)
        assert result == "L'opération a réussi."

    def test_get_translated_message_with_placeholders(self):
        """Test getting message with placeholders."""
        placeholders = {"record": "user"}
        result = get_translated_message("RecordCreated", placeholders, SupportedLanguage.ENGLISH)
        assert result == "The user was successfully created."

    def test_get_translated_message_arabic_with_placeholders(self):
        """Test Arabic translation with placeholders."""
        placeholders = {"record": "المستخدم"}
        result = get_translated_message("RecordCreated", placeholders, SupportedLanguage.ARABIC)
        assert result == "تم إنشاء المستخدم بنجاح."

    def test_get_translated_message_spanish_with_placeholders(self):
        """Test Spanish translation with placeholders."""
        placeholders = {"record": "usuario"}
        result = get_translated_message("RecordDeleted", placeholders, SupportedLanguage.SPANISH)
        assert result == "El usuario se eliminó correctamente."

    def test_get_translated_message_german_with_placeholders(self):
        """Test German translation with placeholders."""
        placeholders = {"records": "Benutzer"}
        result = get_translated_message("RecordsRetrieved", placeholders, SupportedLanguage.GERMAN)
        assert result == "Die Benutzer wurden erfolgreich abgerufen."

    def test_get_translated_message_missing_key_fallback_to_english(self):
        """Test fallback to English when message key is missing in target language."""

        result = get_translated_message("NonExistentKey", language=SupportedLanguage.FRENCH)
        assert result == "NonExistentKey"

    def test_get_translated_message_missing_key_in_all_languages(self):
        """Test when message key doesn't exist in any language."""
        result = get_translated_message("CompletelyMissingKey")
        assert result == "CompletelyMissingKey"

    def test_get_translated_message_missing_placeholder(self):
        """Test behavior when placeholder is missing - should handle KeyError gracefully."""

        result = get_translated_message("RecordCreated", {}, SupportedLanguage.ENGLISH)

        assert result == "The {record} was successfully created."

    def test_get_translated_message_empty_placeholders(self):
        """Test with empty placeholders dictionary."""
        result = get_translated_message("OperationSuccessful", {}, SupportedLanguage.SPANISH)
        assert result == "La operación fue exitosa."

    def test_get_translated_message_none_placeholders(self):
        """Test with None placeholders."""
        result = get_translated_message("OperationSuccessful", None, SupportedLanguage.GERMAN)
        assert result == "Der Vorgang war erfolgreich."

    def test_get_translated_message_none_language(self):
        """Test with None language (should default to English)."""
        result = get_translated_message("OperationSuccessful", None, None)
        assert result == "The operation was successful."

    def test_get_translated_message_partial_placeholders(self):
        """Test with partial placeholders (some missing)."""

        placeholders = {"record": "user"}
        result = get_translated_message("RecordCreated", placeholders, SupportedLanguage.ENGLISH)
        assert result == "The user was successfully created."

    def test_get_translated_message_extra_placeholders(self):
        """Test with extra placeholders that aren't used in the message."""
        placeholders = {"record": "user", "extra": "unused", "another": "also unused"}
        result = get_translated_message("RecordCreated", placeholders, SupportedLanguage.ENGLISH)
        assert result == "The user was successfully created."

    def test_get_translated_message_format_exception_handling(self):
        """Test exception handling during string formatting."""

        placeholders = {"record": "test{invalid}"}
        result = get_translated_message("RecordCreated", placeholders, SupportedLanguage.ENGLISH)

        assert "test{invalid}" in result

    def test_all_languages_have_same_keys(self):
        """Test that all language dictionaries have the same keys."""
        english_keys = set(TRANSLATIONS[SupportedLanguage.ENGLISH].keys())

        for lang, translations in TRANSLATIONS.items():
            lang_keys = set(translations.keys())
            assert lang_keys == english_keys, f"Language {lang} has different keys than English"

    def test_translations_not_empty(self):
        """Test that all translations are not empty."""
        for lang, translations in TRANSLATIONS.items():
            assert len(translations) > 0, f"No translations found for language {lang}"

            for key, value in translations.items():
                assert value, f"Empty translation for key '{key}' in language {lang}"

    def test_complex_error_message_translations(self):
        """Test complex error messages in different languages."""
        placeholders = {"content": "items"}

        for lang in SupportedLanguage:
            result = get_translated_message("NoContentsFound", placeholders, lang)
            assert (
                "items" in result
                or "éléments" in result
                or "contenido" in result
                or "Inhalt" in result
                or "عناصر" in result
            )

    def test_format_error_with_invalid_placeholder_format(self):
        """Test format error handling with invalid placeholder format."""

        import unittest.mock

        with unittest.mock.patch("app.api.i18n.logger"):

            placeholders = {"invalid": None}
            result = get_translated_message("RecordCreated", placeholders, SupportedLanguage.ENGLISH)

            assert "{record}" in result
