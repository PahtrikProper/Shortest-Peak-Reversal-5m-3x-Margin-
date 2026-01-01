using UnityEngine;

namespace UnityApp.ShortTraderMultiFilter
{
    public static class AlertAudio
    {
        public static AudioSource EnsureAudioSource(GameObject host)
        {
            var source = host.GetComponent<AudioSource>() ?? host.AddComponent<AudioSource>();
            source.playOnAwake = false;
            source.loop = false;
            source.clip = source.clip ?? CreateToneClip();
            return source;
        }

        public static void Play(AudioSource source)
        {
            if (source.clip == null)
            {
                source.clip = CreateToneClip();
            }

            source.Stop();
            source.Play();

#if UNITY_ANDROID
            Handheld.Vibrate();
#endif
        }

        private static AudioClip CreateToneClip(float frequency = 880f, float durationSeconds = 0.25f)
        {
            var sampleRate = 44100;
            var totalSamples = Mathf.CeilToInt(sampleRate * durationSeconds);
            var data = new float[totalSamples];

            for (var i = 0; i < totalSamples; i++)
            {
                var t = (float)i / sampleRate;
                data[i] = Mathf.Sin(2 * Mathf.PI * frequency * t) * 0.25f;
            }

            var clip = AudioClip.Create("alert-tone", totalSamples, 1, sampleRate, false);
            clip.SetData(data, 0);
            return clip;
        }
    }
}
