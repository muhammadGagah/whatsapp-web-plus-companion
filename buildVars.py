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
		"Makes WhatsApp Stable and Beta from Microsoft Store easier to use with NVDA, with WhatsApp Web Plus features, keyboard navigation, message reading and call controls.",
	),
	addon_version="2026.11.07",
	addon_changelog=_(
		"Run WhatsApp Stable and Beta together, connect automatically when WhatsApp opens, and choose which WhatsApp to force close. Fixes launch failures on slow computers. Requires NVDA 2025.1 or later.",
	),
	addon_author="Muhammad <muha.aku@gmail.com>",
	addon_url="https://github.com/muhammadGagah/whatsapp-web-plus-companion",
	addon_sourceURL="https://github.com/muhammadGagah/whatsapp-web-plus-companion",
	addon_docFileName="readme.html",
	addon_minimumNVDAVersion="2025.1",
	addon_lastTestedNVDAVersion="2026.2",
	addon_updateChannel=None,
	addon_license="GPL-2.0",
	addon_licenseURL="https://www.gnu.org/licenses/gpl-2.0.html",
)

pythonSources = [
	"addon/globalPlugins/whatsappWebPlusCompanion/*.py",
	"addon/appModules/*.py",
	"addon/appModules/wwpCallSupport/*.py",
]
packageResourceSources = ["addon/globalPlugins/whatsappWebPlusCompanion/resources/**/*"]
i18nSources: list[str] = pythonSources + ["buildVars.py"]
excludedFiles = ["*.pyc", "__pycache__"]
baseLanguage: str = "en"
markdownExtensions: list[str] = ["tables"]
brailleTables: BrailleTables = {}
symbolDictionaries: SymbolDictionaries = {}
speechDictionaries: SpeechDictionaries = {}
