"""Per-traversal UIA property caching; activation always uses live elements."""

PROPERTIES = (
	"ProcessId",
	"FrameworkId",
	"IsEnabled",
	"IsOffscreen",
	"Name",
	"ClassName",
	"ControlType",
	"NativeWindowHandle",
	"AutomationId",
)


class CachedElement:
	def __init__(self, element):
		self.liveElement = element

	def __getattr__(self, name):
		if name.startswith("current") and name[7:] in PROPERTIES:
			return getattr(self.liveElement, "cached" + name[7:])
		return getattr(self.liveElement, name)


def wrap(element):
	return CachedElement(element) if element else None


class CachedWalker:
	def __init__(self, walker, request):
		self.walker = walker
		self.request = request

	def GetFirstChildElement(self, element):
		return wrap(self.walker.GetFirstChildElementBuildCache(element.liveElement, self.request))

	def GetNextSiblingElement(self, element):
		return wrap(self.walker.GetNextSiblingElementBuildCache(element.liveElement, self.request))


def cachedTraversal(client, root, uia):
	"""Cache only one element per provider call, retaining full tree scope.

	No persistent cache and no descendants bulk fetch: traversal node/time limits
	still apply. Cache setup failure falls back to the existing read-only walk.
	"""
	try:
		request = client.CreateCacheRequest()
		request.TreeScope = uia.TreeScope_Element
		request.AutomationElementMode = uia.AutomationElementMode_Full
		for name in PROPERTIES:
			request.AddProperty(getattr(uia, "UIA_" + name + "PropertyId"))
		return wrap(root.BuildUpdatedCache(request)), CachedWalker(client.RawViewWalker, request)
	except Exception:
		return root, client.RawViewWalker
