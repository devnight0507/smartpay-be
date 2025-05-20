"""
Internationalization (i18n) support for API responses.

This module provides translation functionality for API responses
based on the Accept-Language header.
"""

from enum import Enum
from typing import Dict, Optional

from fastapi import Request
from loguru import logger


class SupportedLanguage(str, Enum):
    """Supported languages for translation."""

    ENGLISH = "en"
    ARABIC = "ar"
    FRENCH = "fr"
    SPANISH = "es"
    GERMAN = "de"

    @classmethod
    def get_default(cls) -> "SupportedLanguage":
        """Get default language."""
        return cls.ENGLISH


# Translation dictionaries for each supported language
TRANSLATIONS: Dict[SupportedLanguage, Dict[str, str]] = {
    # English translations (default/fallback)
    SupportedLanguage.ENGLISH: {
        # Success messages
        "RecordCreated": "The {record} was successfully created.",
        "RecordUpdated": "The {record} was successfully updated.",
        "RecordDeleted": "The {record} was successfully deleted.",
        "RecordRetrieved": "The {record} was successfully retrieved.",
        "RecordsRetrieved": "The {records} were successfully retrieved.",
        "OperationSuccessful": "The operation was successful.",
        # Error messages
        "ValidationError": "Validation error occurred. Please check your input data.",
        "RecordNotFound": "The requested {record} was not found.",
        "NoContentsFound": "No {content} were found matching your criteria.",
        "DuplicateRecord": "A {record} with the provided information already exists.",
        "UnauthorizedAccess": "You are not authorized to access this resource.",
        "UnauthenticatedAccess": "Authentication is required to access this resource.",
        "JWTMalformedForbidden": "The provided JWT token is malformed or invalid.",
        "InvalidAuthCredForbidden": "The provided authentication credentials are invalid.",
        "AgentNotExistsForbidden": "The agent specified in the request does not exist.",
        "AgentHasProcessingJobs": "The agent already has processing jobs that must be completed first.",
        "InternalError": "An internal server error occurred. Please try again later.",
    },
    # Arabic translations
    SupportedLanguage.ARABIC: {
        # Success messages
        "RecordCreated": "تم إنشاء {record} بنجاح.",
        "RecordUpdated": "تم تحديث {record} بنجاح.",
        "RecordDeleted": "تم حذف {record} بنجاح.",
        "RecordRetrieved": "تم استرجاع {record} بنجاح.",
        "RecordsRetrieved": "تم استرجاع {records} بنجاح.",
        "OperationSuccessful": "تمت العملية بنجاح.",
        # Error messages
        "ValidationError": "حدث خطأ في التحقق من الصحة. يرجى التحقق من بيانات الإدخال الخاصة بك.",
        "RecordNotFound": "لم يتم العثور على {record} المطلوب.",
        "NoContentsFound": "لم يتم العثور على {content} مطابقة لمعاييرك.",
        "DuplicateRecord": "{record} بالمعلومات المقدمة موجود بالفعل.",
        "UnauthorizedAccess": "أنت غير مصرح لك بالوصول إلى هذا المورد.",
        "UnauthenticatedAccess": "المصادقة مطلوبة للوصول إلى هذا المورد.",
        "JWTMalformedForbidden": "رمز JWT المقدم غير صحيح أو غير صالح.",
        "InvalidAuthCredForbidden": "بيانات اعتماد المصادقة المقدمة غير صالحة.",
        "AgentNotExistsForbidden": "الوكيل المحدد في الطلب غير موجود.",
        "AgentHasProcessingJobs": "لدى الوكيل بالفعل وظائف معالجة يجب إكمالها أولاً.",
        "InternalError": "حدث خطأ داخلي في الخادم. الرجاء المحاولة مرة أخرى لاحقاً.",
    },
    # French translations
    SupportedLanguage.FRENCH: {
        # Success messages
        "RecordCreated": "Le {record} a été créé avec succès.",
        "RecordUpdated": "Le {record} a été mis à jour avec succès.",
        "RecordDeleted": "Le {record} a été supprimé avec succès.",
        "RecordRetrieved": "Le {record} a été récupéré avec succès.",
        "RecordsRetrieved": "Les {records} ont été récupérés avec succès.",
        "OperationSuccessful": "L'opération a réussi.",
        # Error messages
        "ValidationError": "Une erreur de validation s'est produite. Veuillez vérifier vos données d'entrée.",
        "RecordNotFound": "Le {record} demandé n'a pas été trouvé.",
        "NoContentsFound": "Aucun {content} ne correspond à vos critères.",
        "DuplicateRecord": "Un {record} avec les informations fournies existe déjà.",
        "UnauthorizedAccess": "Vous n'êtes pas autorisé à accéder à cette ressource.",
        "UnauthenticatedAccess": "L'authentification est requise pour accéder à cette ressource.",
        "JWTMalformedForbidden": "Le jeton JWT fourni est malformé ou invalide.",
        "InvalidAuthCredForbidden": "Les informations d'authentification fournies sont invalides.",
        "AgentNotExistsForbidden": "L'agent spécifié dans la demande n'existe pas.",
        "AgentHasProcessingJobs": "L'agent a déjà des tâches en cours de traitement qui doivent être terminées d'abord.",  # noqa: E501
        "InternalError": "Une erreur interne du serveur s'est produite. Veuillez réessayer plus tard.",
    },
    # Spanish translations
    SupportedLanguage.SPANISH: {
        # Success messages
        "RecordCreated": "El {record} se creó correctamente.",
        "RecordUpdated": "El {record} se actualizó correctamente.",
        "RecordDeleted": "El {record} se eliminó correctamente.",
        "RecordRetrieved": "El {record} se recuperó correctamente.",
        "RecordsRetrieved": "Los {records} se recuperaron correctamente.",
        "OperationSuccessful": "La operación fue exitosa.",
        # Error messages
        "ValidationError": "Se produjo un error de validación. Por favor, compruebe sus datos de entrada.",
        "RecordNotFound": "No se encontró el {record} solicitado.",
        "NoContentsFound": "No se encontraron {content} que coincidan con sus criterios.",
        "DuplicateRecord": "Ya existe un {record} con la información proporcionada.",
        "UnauthorizedAccess": "No está autorizado para acceder a este recurso.",
        "UnauthenticatedAccess": "Se requiere autenticación para acceder a este recurso.",
        "JWTMalformedForbidden": "El token JWT proporcionado está malformado o no es válido.",
        "InvalidAuthCredForbidden": "Las credenciales de autenticación proporcionadas no son válidas.",
        "AgentNotExistsForbidden": "El agente especificado en la solicitud no existe.",
        "AgentHasProcessingJobs": "El agente ya tiene trabajos en proceso que deben completarse primero.",
        "InternalError": "Se produjo un error interno del servidor. Por favor, inténtelo de nuevo más tarde.",
    },
    # German translations
    SupportedLanguage.GERMAN: {
        # Success messages
        "RecordCreated": "Der {record} wurde erfolgreich erstellt.",
        "RecordUpdated": "Der {record} wurde erfolgreich aktualisiert.",
        "RecordDeleted": "Der {record} wurde erfolgreich gelöscht.",
        "RecordRetrieved": "Der {record} wurde erfolgreich abgerufen.",
        "RecordsRetrieved": "Die {records} wurden erfolgreich abgerufen.",
        "OperationSuccessful": "Der Vorgang war erfolgreich.",
        # Error messages
        "ValidationError": "Es ist ein Validierungsfehler aufgetreten. Bitte überprüfen Sie Ihre Eingabedaten.",
        "RecordNotFound": "Der angeforderte {record} wurde nicht gefunden.",
        "NoContentsFound": "Es wurden keine {content} gefunden, die Ihren Kriterien entsprechen.",
        "DuplicateRecord": "Ein {record} mit den angegebenen Informationen existiert bereits.",
        "UnauthorizedAccess": "Sie sind nicht berechtigt, auf diese Ressource zuzugreifen.",
        "UnauthenticatedAccess": "Für den Zugriff auf diese Ressource ist eine Authentifizierung erforderlich.",
        "JWTMalformedForbidden": "Das bereitgestellte JWT-Token ist fehlerhaft oder ungültig.",
        "InvalidAuthCredForbidden": "Die angegebenen Authentifizierungsdaten sind ungültig.",
        "AgentNotExistsForbidden": "Der in der Anfrage angegebene Agent existiert nicht.",
        "AgentHasProcessingJobs": "Der Agent hat bereits laufende Aufträge, die zuerst abgeschlossen werden müssen.",
        "InternalError": "Ein interner Serverfehler ist aufgetreten. Bitte versuchen Sie es später noch einmal.",
    },
}


def get_preferred_language(request: Request) -> SupportedLanguage:
    """
    Extract the preferred language from the Accept-Language header.

    Args:
        request: The FastAPI request object

    Returns:
        The preferred language code
    """
    accept_language = request.headers.get("Accept-Language", "")

    # Parse the Accept-Language header
    if accept_language:
        # Split by comma and extract language codes
        languages = [lang.split(";")[0].strip() for lang in accept_language.split(",")]

        # Look for exact matches first
        for lang in languages:
            try:
                return SupportedLanguage(lang)
            except ValueError:
                pass

        # Look for partial matches (e.g., "en-US" should match "en")
        for lang in languages:
            base_lang = lang.split("-")[0]
            try:
                return SupportedLanguage(base_lang)
            except ValueError:
                pass

    # Default to English if no supported language is found
    return SupportedLanguage.get_default()


def get_translated_message(
    message_key: str,
    placeholders: Optional[Dict[str, str]] = None,
    language: Optional[SupportedLanguage] = None,
) -> str:
    """
    Get a translated message for the given key and language.

    Args:
        message_key: The key of the message to translate
        placeholders: Optional placeholders to fill in the message
        language: Optional language code (defaults to English)

    Returns:
        The translated message
    """
    lang = language or SupportedLanguage.get_default()
    placeholders = placeholders or {}

    # Get the translation dictionary for the language
    translations = TRANSLATIONS.get(lang, TRANSLATIONS[SupportedLanguage.get_default()])

    # Get the message template or fall back to the default language
    template = translations.get(
        message_key, TRANSLATIONS[SupportedLanguage.get_default()].get(message_key, message_key)
    )

    # Format the message with placeholders
    try:
        return template.format(**placeholders)
    except KeyError as e:
        logger.warning(f"Missing placeholder {e} in translation for {message_key}")
        return template
    except Exception as e:
        logger.error(f"Error formatting translation for {message_key}: {e}")
        return template
