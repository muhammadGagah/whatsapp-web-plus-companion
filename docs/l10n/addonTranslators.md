# Translation Guide for Translators

## Overview

Many NVDA add-ons use the NVDA Add-ons Crowdin project (`nvdaaddons`) to manage translations.

You can contribute translations for both the interface and the documentation.

Translations are synchronized back to add-on repositories through the localization workflow provided by the NVDA Add-on Template.

## Joining the Translation Community

Before you start translating, consider subscribing to the NVDA Translations mailing list.

It is the main place to discuss translation in the NVDA community.

## NVDA Translations Mailing List

The NVDA community maintains the NVDA Translations mailing list on Groups.io.

Use the mailing list to:

* Discuss translation-related topics.
* Request access to translation teams.
* Coordinate translation efforts.
* Report translation issues.
* Discuss problems affecting translation tools or workflows.

You can subscribe at:

https://groups.io/g/nvda-translations

You can ask questions, request access to a translation team, and get help from other translators and maintainers on the list.

## Joining the Translation Project

To contribute translations:

1. Create a Crowdin account.
1. Subscribe to the NVDA Translations mailing list.
1. Request access to the appropriate translation team if necessary.
1. Join the NVDA Add-ons Crowdin project.
1. Select the language you want to translate.
1. Begin translating interface strings and documentation.

## Translation Methods

You can translate in Crowdin's web interface or use translation tools on your computer.

### Crowdin Web Editor

With Crowdin's web editor, you can:

* Translate strings online.
* Review existing translations.
* Suggest improvements.
* Vote on translation proposals.

You do not need to install any extra software.

### Poedit

Many NVDA translators prefer to work locally using [Poedit](https://poedit.com/) because of its accessibility and ease of use.

Poedit supports both:

* Portable Object (`.po`) files used for interface translations.
* XLIFF (`.xliff`) files used for documentation translations.

After completing translations locally, files can be uploaded back to Crowdin using [l10nUtil.exe](https://github.com/nvaccess/nvdaL10n/releases/latest).

## Translating Interface Strings

Interface translations are stored in Portable Object (`.po`) files.

These files can be translated either:

* Directly in Crowdin.
* Using Poedit.

## Translating Documentation

Documentation translations are stored in XLIFF (`.xliff`) files.

These files are generated automatically from the add-on documentation.

Documentation can be translated:

* Directly in Crowdin.
* Using Poedit.

When translating documentation:

* Translate only the text content.
* Preserve placeholders and formatting.
* Do not modify the XLIFF structure manually.

## Uploading Offline Translations

After translating files on your computer, upload them to Crowdin with [l10nUtil.exe](https://github.com/nvaccess/nvdaL10n/releases/latest).

Examples:

```cmd
l10nUtil.exe uploadTranslationFile fr addonName.po -c addon
```

```cmd
l10nUtil.exe uploadTranslationFile fr addonName.xliff -c addon
```

In these examples:

* `fr` is the Crowdin language code.
* `addonName.po` is a translated interface file.
* `addonName.xliff` is a translated documentation file.

Once uploaded, the translations become available in Crowdin and can later be synchronized back into the add-on repository.

## Using l10nUtil.exe

To display the complete list of available commands:

```cmd
l10nUtil.exe --help
```

or:

```cmd
l10nUtil.exe -h
```

To display help for a specific command:

```cmd
l10nUtil.exe downloadTranslationFile --help
```

or:

```cmd
l10nUtil.exe downloadTranslationFile -h
```

Refer to the utility help output for a complete list of supported commands and options.

## How Synchronization Works

Translations are not immediately imported into GitHub repositories.

The add-on maintainer runs a synchronization workflow that:

1. Connects to the NVDA Add-ons Crowdin project.
1. Downloads completed translations.
1. Verifies their translation completion percentage.
1. Synchronizes eligible translations back into the repository.

The add-on maintainer can set a minimum completion percentage. Translations must reach this threshold before the workflow imports them.

## Why Has My Translation Not Appeared Yet?

Possible reasons include:

* The synchronization workflow has not yet run.
* The required translation completion percentage has not yet been reached.
* The maintainer has temporarily disabled synchronization.
* The translation was completed after the most recent synchronization cycle.

## Best Practices

To improve translation quality:

* Use existing terminology consistently.
* Preserve placeholders and formatting.
* Review existing translations before introducing new terminology.
* Coordinate with other translators whenever possible.
* Test translated files locally before uploading them when possible.

## Reporting Problems

If you encounter translation issues:

* Contact the add-on maintainer.
* Open an issue in the add-on repository if appropriate.
* Ask for help on the NVDA Translations mailing list.
* Discuss translation-related issues with the NVDA translation community.

## Frequently Asked Questions

### Can I translate both documentation and interface strings?

Yes. The NVDA Add-ons Crowdin project supports both interface translations (`.po`) and documentation translations (`.xliff`).

### Do I need to use the Crowdin web interface?

No. You can work directly in Crowdin, or use Poedit and upload your completed translations with `l10nUtil.exe`.

Both approaches are supported by the NVDA Add-ons translation workflow.

### Do I need access to GitHub?

Not necessarily. Most translators use Crowdin or local translation tools with `l10nUtil.exe`.

The add-on maintainer manages the workflow that automatically imports translations into GitHub repositories.

### Can I force synchronization?

No. The add-on maintainer controls synchronization through the localization workflow provided by the NVDA Add-on Template.
