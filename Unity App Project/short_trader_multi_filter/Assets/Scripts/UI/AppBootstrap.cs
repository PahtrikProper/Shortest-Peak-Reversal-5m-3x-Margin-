using UnityEngine;

namespace UnityApp.ShortTraderMultiFilter
{
    [DefaultExecutionOrder(-1000)]
    public class AppBootstrap : MonoBehaviour
    {
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        private static void AutoCreate()
        {
            if (FindObjectOfType<AppBootstrap>() != null)
            {
                return;
            }

            var go = new GameObject("AppBootstrap");
            go.AddComponent<AppBootstrap>();
            DontDestroyOnLoad(go);
        }

        private void Awake()
        {
            var canvas = UiBuilder.EnsureCanvas();
            var refs = UiBuilder.CreateUi(canvas);

            var controller = FindObjectOfType<TradingUIController>();
            if (controller == null)
            {
                controller = canvas.gameObject.AddComponent<TradingUIController>();
            }

            controller.BindUi(refs);
        }
    }
}
