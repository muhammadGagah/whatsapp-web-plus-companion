"""Choose which Microsoft Store WhatsApp to force close."""

from collections.abc import Callable

import addonHandler
import wx

from .models import Channel

addonHandler.initTranslation()

# Radio button order, in every language: Stable, Beta, then both.
CHOICES: tuple[tuple[Channel, ...] | None, ...] = ((Channel.STABLE,), (Channel.BETA,), None)


def choiceIndex(default: Channel | None) -> int:
	"""Index of the radio button for one channel, or of "all" when no single channel is suggested."""
	for index, choice in enumerate(CHOICES):
		if choice is not None and choice == (default,):
			return index
	return len(CHOICES) - 1


class ForceCloseDialog(wx.Dialog):
	def __init__(
		self,
		parent,
		*,
		default: Channel | None,
		onConfirm: Callable[[tuple[Channel, ...] | None], None],
	) -> None:
		super().__init__(
			parent,
			# Translators: Title of the dialog that force closes Microsoft Store WhatsApp.
			title=_("Force close WhatsApp"),
			style=wx.DEFAULT_DIALOG_STYLE,
		)
		self._onConfirm = onConfirm
		outer = wx.BoxSizer(wx.VERTICAL)
		warning = wx.StaticText(
			self,
			label=_(
				# Translators: Warning in the force-close dialog.
				"The selected WhatsApp closes right away. Calls and file transfers will stop, and unsent text may be lost.",
			),
		)
		warning.Wrap(500)
		outer.Add(warning, flag=wx.ALL | wx.EXPAND, border=10)
		self.choice = wx.RadioBox(
			self,
			# Translators: Label of the radio buttons that choose which WhatsApp to force close.
			label=_("WhatsApp to &close"),
			choices=[
				# Translators: Force-close choice for WhatsApp Stable only.
				_("WhatsApp Stable"),
				# Translators: Force-close choice for WhatsApp Beta only.
				_("WhatsApp Beta"),
				# Translators: Force-close choice for both WhatsApp Stable and WhatsApp Beta.
				_("All (Stable and Beta)"),
			],
			majorDimension=1,
			style=wx.RA_SPECIFY_COLS,
		)
		self.choice.SetSelection(choiceIndex(default))
		outer.Add(self.choice, flag=wx.ALL | wx.EXPAND, border=10)
		buttons = wx.StdDialogButtonSizer()
		# Translators: Destructive button in the force-close dialog.
		confirm = wx.Button(self, wx.ID_OK, label=_("&Force close"))
		# Translators: Safe default button in the force-close dialog.
		cancel = wx.Button(self, wx.ID_CANCEL, label=_("&Keep WhatsApp open"))
		buttons.AddButton(confirm)
		buttons.AddButton(cancel)
		buttons.Realize()
		outer.Add(buttons, flag=wx.ALL | wx.ALIGN_RIGHT, border=10)
		self.SetSizerAndFit(outer)
		self.SetEscapeId(wx.ID_CANCEL)
		# Enter keeps WhatsApp open; closing needs the Force close button.
		cancel.SetDefault()
		confirm.Bind(wx.EVT_BUTTON, self._confirm)
		cancel.Bind(wx.EVT_BUTTON, lambda event: self.Close())
		self.Bind(wx.EVT_CLOSE, lambda event: self.Destroy())
		self.CentreOnScreen()
		self.choice.SetFocus()

	def selectedChannels(self) -> tuple[Channel, ...] | None:
		return CHOICES[self.choice.GetSelection()]

	def _confirm(self, event) -> None:
		channels = self.selectedChannels()
		self.Close()
		self._onConfirm(channels)
