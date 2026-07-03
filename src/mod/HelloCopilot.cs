using System;
using System.Diagnostics;
using System.Drawing;
using System.Globalization;
using System.IO;
using System.Text;
using GTA;
using GTA.UI;

namespace GtaCopilot.Mod
{
    /// <summary>
    /// Script entrypoint. All GTA/SHVDN state reads stay inside OnTick,
    /// throttled by Game.GameTime. The only concurrency in the mod lives in
    /// StateStreamClient (Claude Code owned); OnTick hands it pre-serialized
    /// strings and never blocks on the network.
    /// </summary>
    public sealed class HelloCopilot : Script
    {
        private static readonly PointF HealthTextPosition = new PointF(20.0f, 20.0f);
        private static readonly Encoding Utf8NoBom = new UTF8Encoding(false);
        private const float HealthTextScale = 0.45f;
        private const int PollIntervalMilliseconds = 250;
        private const int HeartbeatIntervalMilliseconds = 5000;
        private const string StateFileName = "GtaCopilot.state.jsonl";

        private readonly GameStateReader stateReader;
        private readonly StateStreamClient streamClient;
        private readonly string stateFilePath;
        private GameState currentState;
        private GameState lastEmittedState;
        private string lastLoggedStreamStatus;
        private int lastPollGameTime = -1;
        private int lastEmitGameTime = -1;
        private int lastExceptionLogGameTime = -1;

        public HelloCopilot()
        {
            Interval = 0;
            stateReader = new GameStateReader();
            streamClient = new StateStreamClient();
            stateFilePath = ResolveStateFilePath();
            Tick += OnTick;
            Aborted += OnAborted;
            Console.WriteLine("GtaCopilot: state reader initialized; writing " + stateFilePath);
        }

        private void OnTick(object sender, EventArgs e)
        {
            int gameTime = -1;

            try
            {
                gameTime = Game.GameTime;
                if (IsDue(gameTime, lastPollGameTime, PollIntervalMilliseconds))
                {
                    currentState = stateReader.Read();
                    lastPollGameTime = gameTime;
                    EmitIfNeeded(currentState, gameTime);
                    LogStreamStatusIfChanged();
                }

                if (currentState != null)
                {
                    DrawHealth(currentState.health);
                }
            }
            catch (Exception ex)
            {
                LogTickException(ex, gameTime);
            }
        }

        private void EmitIfNeeded(GameState state, int gameTime)
        {
            bool changed = lastEmittedState == null || !state.HasSameObservedValues(lastEmittedState);
            bool heartbeat = IsDue(gameTime, lastEmitGameTime, HeartbeatIntervalMilliseconds);

            if (!changed && !heartbeat)
            {
                return;
            }

            string line = JsonWriter.Write(state);

            try
            {
                string directory = Path.GetDirectoryName(stateFilePath);
                if (!string.IsNullOrEmpty(directory))
                {
                    Directory.CreateDirectory(directory);
                }

                File.AppendAllText(stateFilePath, line + Environment.NewLine, Utf8NoBom);
            }
            catch (Exception ex)
            {
                Console.WriteLine("GtaCopilot: failed to append state jsonl: " + ex.Message);
            }

            Console.WriteLine(line);
            streamClient.EnqueueLine(line);
            lastEmittedState = state;
            lastEmitGameTime = gameTime;
        }

        private void LogStreamStatusIfChanged()
        {
            string streamStatus = streamClient.Status;
            if (streamStatus != lastLoggedStreamStatus)
            {
                Console.WriteLine("GtaCopilot: stream " + streamStatus);
                lastLoggedStreamStatus = streamStatus;
            }
        }

        private static void DrawHealth(int health)
        {
            var text = new TextElement(
                "Health: " + health.ToString(CultureInfo.InvariantCulture),
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

        private void LogTickException(Exception ex, int gameTime)
        {
            if (gameTime < 0 || IsDue(gameTime, lastExceptionLogGameTime, HeartbeatIntervalMilliseconds))
            {
                Console.WriteLine("GtaCopilot: OnTick exception: " + ex);
                lastExceptionLogGameTime = gameTime;
            }
        }

        private static bool IsDue(int gameTime, int lastGameTime, int intervalMilliseconds)
        {
            if (lastGameTime < 0 || gameTime < lastGameTime)
            {
                return true;
            }

            return gameTime - lastGameTime >= intervalMilliseconds;
        }

        private static string ResolveStateFilePath()
        {
            try
            {
                using (Process process = Process.GetCurrentProcess())
                {
                    string executablePath = process.MainModule == null ? null : process.MainModule.FileName;
                    string gameRoot = string.IsNullOrEmpty(executablePath) ? null : Path.GetDirectoryName(executablePath);
                    if (!string.IsNullOrEmpty(gameRoot))
                    {
                        return Path.Combine(gameRoot, "scripts", StateFileName);
                    }
                }
            }
            catch
            {
                // Fall through to the relative scripts path. This still matches
                // the requested Phase 1 location if the process cwd is game root.
            }

            return Path.Combine("scripts", StateFileName);
        }

        private void OnAborted(object sender, EventArgs e)
        {
            Tick -= OnTick;
            Aborted -= OnAborted;
            streamClient.Dispose();
            Console.WriteLine("GtaCopilot: state reader aborted.");
        }
    }
}
