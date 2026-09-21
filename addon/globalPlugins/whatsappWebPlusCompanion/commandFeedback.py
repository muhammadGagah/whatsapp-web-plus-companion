"""Speech and braille for explicit command results delivered after the script ends."""


def message(text):
	import speech
	import ui

	getState = getattr(speech, "getState", None)
	modes = getattr(speech, "SpeechMode", None)
	mode = getState().speechMode if getState is not None and modes is not None else None
	if modes is None or mode != modes.onDemand:
		ui.message(text)
		return
	# ui.message is synchronous; never leave talk enabled while a callback is queued.
	speech.setSpeechMode(modes.talk)
	try:
		ui.message(text)
	finally:
		speech.setSpeechMode(mode)
