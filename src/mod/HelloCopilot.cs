using System;
using System.Drawing;
using GTA;
using GTA.UI;

namespace GtaCopilot.Mod
{
    /// <summary>
    /// Phase 0 proof-of-life script. All GTA/SHVDN state reads and drawing stay
    /// inside the SHVDN Tick event, which runs on the main script thread.
    /// </summary>
    public sealed class HelloCopilot : Script
    {
        private static readonly PointF HealthTextPosition = new PointF(20.0f, 20.0f);
        private const float HealthTextScale = 0.45f;

        public HelloCopilot()
        {
            Interval = 0;
            Tick += OnTick;
            Aborted += OnAborted;
        }

        private static void DrawHealth(int health)
        {
            var text = new TextElement(
                $"Health: {health}",
                HealthTextPosition,
                HealthTextScale,
                Color.White,
                GTA.UI.Font.ChaletLondon,
                Alignment.Left)
            {
                Outline = true
            };

            text.Draw();
        }

        private void OnTick(object sender, EventArgs e)
        {
            Ped player = Game.Player.Character;
            DrawHealth(player?.Health ?? 0);
        }

        private void OnAborted(object sender, EventArgs e)
        {
            Tick -= OnTick;
            Aborted -= OnAborted;
        }
    }
}
