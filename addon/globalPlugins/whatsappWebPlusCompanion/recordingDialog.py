"""Accessible native recording setup, shown only after devices have loaded."""

from pathlib import Path

import addonHandler
import wx

from .models import Channel

addonHandler.initTranslation()

# Availability is True, False or None (unknown), so the first refresh needs a distinct marker.
_NOT_SHOWN = object()


def microphoneLabels(devices) -> list[str]:
	return [
		device["name"]
		# Translators: Shown for a microphone that Windows reports without a name.
		or _("Unnamed microphone {number}").format(number=number)
		for number, device in enumerate(devices, 1)
	]


class RecordingDialog(wx.Dialog):
	def __init__(self, parent, *, devices, channel, allowed, callAvailable, onStart, onStatus=None):
		super().__init__(
			parent,
			title=_("Record WhatsApp call"),
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
		)
		self._devices = devices
		self._allowed = allowed
		self._onStart = onStart
		self._callAvailable = callAvailable
		self._onStatus = onStatus
		self._lastAvailable = _NOT_SHOWN
		self._closed = False
		self._pending = False
		self._timer = None
		outer = wx.BoxSizer(wx.VERTICAL)
		intro = wx.StaticText(
			self,
			label=_(
				"Start during a call after informing the participants. Choose the same microphone as WhatsApp. "
				"WhatsApp audio is saved on the left channel and your microphone on the right. "
				"The microphone is recorded even when muted in WhatsApp. Recording stops by itself shortly after the call "
				"window closes; use Stop recording to stop earlier.",
			),
		)
		intro.Wrap(550)
		outer.Add(intro, flag=wx.ALL | wx.EXPAND, border=10)
		outer.Add(wx.StaticText(self, label=_("&WhatsApp channel:")), flag=wx.LEFT, border=10)
		# Index 0 is Channel.STABLE and index 1 is Channel.BETA, in every language.
		self.channel = wx.Choice(self, choices=[_("Stable"), _("Beta")])
		self.channel.SetSelection(0 if channel == Channel.STABLE else 1)
		outer.Add(self.channel, flag=wx.ALL | wx.EXPAND, border=10)
		outer.Add(wx.StaticText(self, label=_("&Microphone:")), flag=wx.LEFT, border=10)
		self.microphone = wx.Choice(self, choices=microphoneLabels(devices))
		self.microphone.SetSelection(0)
		outer.Add(self.microphone, flag=wx.ALL | wx.EXPAND, border=10)
		outer.Add(wx.StaticText(self, label=_("&Recording folder:")), flag=wx.LEFT, border=10)
		self.folder = wx.TextCtrl(
			self,
			value=str(Path(wx.StandardPaths.Get().GetDocumentsDir()) / "WhatsApp Recordings"),
		)
		outer.Add(self.folder, flag=wx.ALL | wx.EXPAND, border=10)
		self._availabilityText = wx.StaticText(self, label="")
		outer.Add(self._availabilityText, flag=wx.ALL | wx.EXPAND, border=10)
		buttons = wx.StdDialogButtonSizer()
		start = wx.Button(self, wx.ID_OK, label=_("&Start recording"))
		self._startButton = start
		cancel = wx.Button(self, wx.ID_CANCEL, label=_("Cancel"))
		self._cancelButton = cancel
		buttons.AddButton(start)
		buttons.AddButton(cancel)
		buttons.Realize()
		outer.Add(buttons, flag=wx.ALL | wx.ALIGN_RIGHT, border=10)
		self.SetSizerAndFit(outer)
		self.SetMinSize(self.GetSize())
		self.SetEscapeId(wx.ID_CANCEL)
		cancel.SetDefault()
		start.Bind(wx.EVT_BUTTON, self._start)
		cancel.Bind(wx.EVT_BUTTON, lambda event: self.Close())
		self.Bind(wx.EVT_CLOSE, self._close)
		self.channel.Bind(wx.EVT_CHOICE, lambda event: self._refresh())
		self.CentreOnScreen()
		self.microphone.SetFocus()
		self._refresh()

	def _close(self, event):
		self._closed = True
		if self._timer is not None:
			self._timer.Stop()
		self.Destroy()

	def _refresh(self):
		if self._closed:
			return
		if self._timer is not None:
			self._timer.Stop()
		if self._pending:
			self._timer = wx.CallLater(2000, self._refresh)
			return
		channel = Channel.STABLE if self.channel.GetSelection() == 0 else Channel.BETA
		# None means the last check failed or expired. Start runs a fresh check, so it stays enabled.
		available = self._callAvailable(channel) if self._allowed() else False
		enabled = available is not False
		if available != self._lastAvailable:
			if available is None:
				# Translators: The call state could not be read; Start still checks before recording.
				text = _("Could not confirm the call window. Start will check again.")
			elif available:
				text = _("Call window detected. Start will verify the connection.")
			else:
				text = _(
					"Call window unavailable. Open the call window or check the selected WhatsApp channel.",
				)
			self._availabilityText.SetLabel(text)
			self._availabilityText.Wrap(550)
			self.Layout()
			if self._lastAvailable is not _NOT_SHOWN and self._onStatus and self._allowed():
				self._onStatus(text)
			self._lastAvailable = available
		if not enabled and self._startButton.HasFocus():
			self._cancelButton.SetFocus()
		self._startButton.Enable(enabled)
		self._timer = wx.CallLater(2000, self._refresh)

	def _start(self, event):
		if self._pending or self._closed:
			return
		if not self._allowed():
			self.Close()
			return
		folder = self.folder.GetValue().strip()
		if not folder or not Path(folder).is_absolute():
			wx.MessageBox(
				_("Choose an absolute path for the recording folder."),
				_("Record WhatsApp call"),
				wx.OK | wx.ICON_ERROR,
				self,
			)
			self.folder.SetFocus()
			return
		channel = Channel.STABLE if self.channel.GetSelection() == 0 else Channel.BETA
		self._pending = True
		self._cancelButton.SetFocus()
		self._startButton.Enable(False)
		self.channel.Enable(False)
		self.microphone.Enable(False)
		self.folder.Enable(False)

		def completed(started):
			if self._closed:
				return
			self._pending = False
			if started:
				self.Close()
			else:
				self.channel.Enable(True)
				self.microphone.Enable(True)
				self.folder.Enable(True)
				self._refresh()

		self._onStart(
			channel,
			self._devices[self.microphone.GetSelection()]["id"],
			folder,
			completed,
			lambda: not self._closed and self._pending,
		)
