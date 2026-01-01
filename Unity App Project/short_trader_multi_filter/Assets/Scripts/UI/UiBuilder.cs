using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

namespace UnityApp.ShortTraderMultiFilter
{
    public static class UiBuilder
    {
        public static Canvas EnsureCanvas()
        {
            var canvas = Object.FindObjectOfType<Canvas>();
            if (canvas != null)
            {
                return canvas;
            }

            var go = new GameObject("Canvas", typeof(Canvas), typeof(CanvasScaler), typeof(GraphicRaycaster));
            canvas = go.GetComponent<Canvas>();
            canvas.renderMode = RenderMode.ScreenSpaceOverlay;

            var scaler = go.GetComponent<CanvasScaler>();
            scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            scaler.referenceResolution = new Vector2(1080, 1920);
            scaler.matchWidthOrHeight = 0.5f;

            EnsureEventSystem();
            return canvas;
        }

        public static void EnsureEventSystem()
        {
            if (Object.FindObjectOfType<EventSystem>() != null)
            {
                return;
            }

            var es = new GameObject("EventSystem", typeof(EventSystem), typeof(StandaloneInputModule));
            Object.DontDestroyOnLoad(es);
        }

        public static UiReferences CreateUi(Canvas canvas)
        {
            var root = new GameObject("UIRoot");
            root.transform.SetParent(canvas.transform, false);
            root.AddComponent<RectTransform>();

            var layout = root.AddComponent<VerticalLayoutGroup>();
            layout.childControlHeight = true;
            layout.childControlWidth = true;
            layout.childForceExpandHeight = false;
            layout.childForceExpandWidth = true;
            layout.spacing = 8;
            layout.padding = new RectOffset(12, 12, 12, 12);

            var statusText = CreateLabel("Status", root.transform, 18, FontStyle.Bold);
            var equityText = CreateLabel("Equity", root.transform, 18, FontStyle.Normal);
            var signalText = CreateLabel("Signals", root.transform, 18, FontStyle.Normal);

            var scrollGo = new GameObject("LogScroll", typeof(Image), typeof(ScrollRect));
            scrollGo.transform.SetParent(root.transform, false);
            var image = scrollGo.GetComponent<Image>();
            image.color = new Color(0f, 0f, 0f, 0.3f);
            var rect = scrollGo.AddComponent<RectTransform>();
            rect.sizeDelta = new Vector2(0, 400);

            var viewport = new GameObject("Viewport", typeof(Mask), typeof(Image));
            viewport.transform.SetParent(scrollGo.transform, false);
            var viewportRect = viewport.GetComponent<RectTransform>();
            viewportRect.anchorMin = Vector2.zero;
            viewportRect.anchorMax = Vector2.one;
            viewportRect.offsetMin = Vector2.zero;
            viewportRect.offsetMax = Vector2.zero;
            viewport.GetComponent<Image>().color = new Color(0, 0, 0, 0.2f);
            viewport.GetComponent<Mask>().showMaskGraphic = false;

            var content = new GameObject("Content", typeof(RectTransform));
            content.transform.SetParent(viewport.transform, false);
            var contentRect = content.GetComponent<RectTransform>();
            contentRect.anchorMin = new Vector2(0, 1);
            contentRect.anchorMax = new Vector2(1, 1);
            contentRect.pivot = new Vector2(0.5f, 1);
            var fitter = content.AddComponent<ContentSizeFitter>();
            fitter.verticalFit = ContentSizeFitter.FitMode.PreferredSize;
            fitter.horizontalFit = ContentSizeFitter.FitMode.Unconstrained;

            var logText = CreateLabel("Logs", content.transform, 14, FontStyle.Normal, TextAnchor.UpperLeft);
            var logRect = logText.rectTransform;
            logRect.anchorMin = new Vector2(0, 1);
            logRect.anchorMax = new Vector2(1, 1);
            logRect.pivot = new Vector2(0.5f, 1);

            var scroll = scrollGo.GetComponent<ScrollRect>();
            scroll.viewport = viewportRect;
            scroll.content = contentRect;
            scroll.horizontal = false;
            scroll.vertical = true;

            var audioSource = AlertAudio.EnsureAudioSource(root);

            return new UiReferences(statusText, equityText, signalText, logText, audioSource, scroll);
        }

        private static Text CreateLabel(string text, Transform parent, int fontSize, FontStyle fontStyle, TextAnchor alignment = TextAnchor.UpperLeft)
        {
            var go = new GameObject(text, typeof(Text));
            go.transform.SetParent(parent, false);
            var label = go.GetComponent<Text>();
            label.text = text;
            label.fontSize = fontSize;
            label.fontStyle = fontStyle;
            label.color = Color.white;
            label.alignment = alignment;
            label.horizontalOverflow = HorizontalWrapMode.Wrap;
            label.verticalOverflow = VerticalWrapMode.Overflow;
            label.font = Resources.GetBuiltinResource<Font>("Arial.ttf");
            return label;
        }
    }

    public record UiReferences(Text Status, Text Equity, Text Signals, Text Log, AudioSource Audio, ScrollRect Scroll);
}
