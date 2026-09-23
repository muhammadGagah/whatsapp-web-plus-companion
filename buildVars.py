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
		"WhatsApp Companion makes Microsoft Store WhatsApp Stable and Beta easier to use with NVDA. It brings WhatsApp Web Plus features to the desktop app, with keyboard navigation, message reading, and call controls with customizable labels.",
	),
	addon_version="2026.09.23",
	addon_changelog=_(
		"Read and copy messages in NVDA, record custom shortcuts, and browse the shortcut list. Improved call controls, WebView2 permission repair, and NVDA compatibility. Includes WhatsApp Web Plus 2.6.84. Requires NVDA 2025.1 or later.",
	),
	addon_author="Muhammad",
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
