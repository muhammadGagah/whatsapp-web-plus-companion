from site_scons.site_tools.NVDATool.typings import (
	AddonInfo,
	BrailleTables,
	SymbolDictionaries,
	SpeechDictionaries,
)
from site_scons.site_tools.NVDATool.utils import _

addon_info = AddonInfo(
	addon_name="whatsappWebPlusCompanion",
	addon_summary=_("WhatsApp Companion"),
	addon_description=_(
		"WhatsApp Companion brings fast keyboard navigation and clearer screen-reader feedback from WhatsApp Web Plus to Microsoft Store WhatsApp Stable and Beta. It securely loads a bundled, verified userscript and restores the connection automatically when WhatsApp replaces its renderer.",
	),
	addon_version="2026.08.16",
	addon_changelog=_(
		"Renamed the visible add-on to WhatsApp Companion, added random session tokens, context nonces, and semantic health validation across renderer reloads, hardened stale speech and braille announcement invalidation, and bundled WhatsApp Web Plus 2.6.76.",
	),
	addon_author="Muhammad",
	addon_url="https://github.com/muhammadGagah/whatsapp-web-plus-companion",
	addon_sourceURL="https://github.com/muhammadGagah/whatsapp-web-plus-companion",
	addon_docFileName="readme.html",
	addon_minimumNVDAVersion="2024.1.0",
	addon_lastTestedNVDAVersion="2026.1.1",
	addon_updateChannel=None,
	addon_license="GPL-2.0",
	addon_licenseURL="https://www.gnu.org/licenses/gpl-2.0.html",
)

pythonSources = ["addon/globalPlugins/whatsappWebPlusCompanion/*.py"]
i18nSources: list[str] = pythonSources + ["buildVars.py"]
excludedFiles = ["*.pyc", "__pycache__"]
baseLanguage: str = "en"
markdownExtensions: list[str] = ["tables"]
brailleTables: BrailleTables = {}
symbolDictionaries: SymbolDictionaries = {}
speechDictionaries: SpeechDictionaries = {}
