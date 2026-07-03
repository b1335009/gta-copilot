using System;
using System.Diagnostics;
using System.Drawing;
using System.Globalization;
using System.IO;
using System.Text;
using GTA;
using GTA.Math;
using GTA.Native;
using GTA.UI;

namespace GtaCopilot.Mod
{
    /// <summary>
    /// Script entrypoint. All GTA/SHVDN state reads AND action execution
    /// stay inside OnTick, throttled by Game.GameTime. The only concurrency
    /// in the mod lives in StateStreamClient (Claude Code owned); OnTick
    /// hands it pre-serialized strings and never blocks on the network.
    ///
    /// Phase 5a: OnTick drains ≤1 action per tick from ActionReceiver,
    /// validates it against the compiled-in whitelist, executes the native
    /// on the script thread, and emits an ack line back through the stream.
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
        private readonly ActionReceiver actionReceiver;
        private readonly StateStreamClient streamClient;
        private Ped companion;
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
            actionReceiver = new ActionReceiver();
            streamClient = new StateStreamClient(actionReceiver);
            stateFilePath = ResolveStateFilePath();
            Tick += OnTick;
            Aborted += OnAborted;
            Console.WriteLine("GtaCopilot: state reader initialized (Phase 5a); writing " + stateFilePath);
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

                // Phase 5a: drain ≤1 action per tick from the inbound queue
                DrainOneAction();
            }
            catch (Exception ex)
            {
                LogTickException(ex, gameTime);
            }
        }

        // ------------------------------------------------------------------
        // Phase 5a: action execution on the script thread
        // ------------------------------------------------------------------

        private void DrainOneAction()
        {
            ActionReceiver.ActionRequest action = actionReceiver.TryDequeue();
            if (action == null)
            {
                return;
            }

            Console.WriteLine("GtaCopilot: executing action id=" +
                action.id.ToString(CultureInfo.InvariantCulture) + " " + action.action);

            string err = null;
            bool ok = false;

            try
            {
                switch (action.action)
                {
                    case "set_waypoint":
                        ExecuteSetWaypoint(action.paramX, action.paramY);
                        ok = true;
                        break;

                    case "heal_player":
                        // Whitelisted, but execution is gated to Phase 5c —
                        // one action per phase, tested individually.
                        err = "heal_player not enabled until Phase 5c";
                        break;

                    case "spawn_companion":
                        err = ExecuteSpawnCompanion();
                        ok = err == null;
                        break;

                    default:
                        err = "unknown action: " + action.action;
                        break;
                }
            }
            catch (Exception ex)
            {
                err = "execution error: " + ex.Message;
                Console.WriteLine("GtaCopilot: action execution error: " + ex);
            }

            // Emit ack back to the brain
            string ackLine = ActionReceiver.BuildAck(action.id, ok, err);
            Console.WriteLine("GtaCopilot: ack -> " + ackLine);
            streamClient.EnqueueAck(ackLine);
        }

        /// <summary>
        /// Spawn one armed companion ped that joins the player's group
        /// (group AI provides follow + defend). Exactly one companion may be
        /// alive at a time; respawn is allowed after it dies. Returns null on
        /// success or an error string for the nack. Script thread only.
        /// </summary>
        private string ExecuteSpawnCompanion()
        {
            if (companion != null && companion.Exists() && !companion.IsDead)
            {
                return "companion already active";
            }

            if (companion != null)
            {
                companion.MarkAsNoLongerNeeded();
                companion = null;
            }

            Ped player = Game.Player.Character;
            if (player == null || !player.Exists())
            {
                return "player ped unavailable";
            }

            var model = new Model(PedHash.Bouncer01SMM);
            model.Request(1000);
            if (!model.IsLoaded)
            {
                return "companion model not loaded; try again";
            }

            Vector3 spawnPosition = player.Position + player.RightVector * 2.0f;
            Ped ped = World.CreatePed(model, spawnPosition);
            model.MarkAsNoLongerNeeded();
            if (ped == null)
            {
                return "ped creation failed";
            }

            ped.IsPersistent = true;
            ped.Armor = 100;
            ped.Weapons.Give(WeaponHash.Pistol, 250, true, true);
            ped.RelationshipGroup = player.RelationshipGroup;

            int playerGroup = Function.Call<int>(Hash.GET_PLAYER_GROUP, Game.Player.Handle);
            Function.Call(Hash.SET_PED_AS_GROUP_MEMBER, ped.Handle, playerGroup);
            Function.Call(Hash.SET_PED_NEVER_LEAVES_GROUP, ped.Handle, true);
            Function.Call(Hash.SET_PED_COMBAT_ATTRIBUTES, ped.Handle, 46, true); // BF_CanFightArmedPedsWhenNotArmed group defense

            Blip blip = ped.AddBlip();
            if (blip != null)
            {
                blip.Color = BlipColor.Blue;
            }

            companion = ped;
            Console.WriteLine("GtaCopilot: companion spawned (handle " +
                ped.Handle.ToString(CultureInfo.InvariantCulture) + ")");
            return null;
        }

        /// <summary>
        /// Set a waypoint on the player's map at the given world coordinates.
        /// Uses the native SET_NEW_WAYPOINT which naturally takes 2D map coords.
        /// Must be called on the script thread.
        /// </summary>
        private static void ExecuteSetWaypoint(float x, float y)
        {
            Function.Call(Hash.SET_NEW_WAYPOINT, x, y);
            Console.WriteLine("GtaCopilot: waypoint set at x=" +
                x.ToString("F1", CultureInfo.InvariantCulture) + " y=" +
                y.ToString("F1", CultureInfo.InvariantCulture));
        }

        // ------------------------------------------------------------------
        // Existing Phase 1–2 methods (unchanged)
        // ------------------------------------------------------------------

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
            if (companion != null && companion.Exists())
            {
                companion.MarkAsNoLongerNeeded();
                companion = null;
            }
            streamClient.Dispose();
            Console.WriteLine("GtaCopilot: state reader aborted.");
        }
    }
}
