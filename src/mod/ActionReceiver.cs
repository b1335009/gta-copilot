using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text;

namespace GtaCopilot.Mod
{
    /// <summary>
    /// Phase 5a — reverse command channel. Parses inbound action JSON from the
    /// brain, queues validated requests for the script thread, and builds ack lines.
    ///
    /// Threading contract:
    ///   - The reader thread (inside StateStreamClient) calls <see cref="ParseAndEnqueue"/>
    ///     with raw UTF-8 lines read from the TCP stream.
    ///   - The script thread (OnTick) calls <see cref="TryDequeue"/> to pull at most
    ///     one action per tick, then calls <see cref="BuildAck"/> with the result.
    ///   - Queue is bounded (drop-newest when full) per PROJECT_STATE.md spec.
    ///
    /// Whitelist is compiled-in and must mirror ACTION_WHITELIST.md exactly.
    /// </summary>
    public sealed class ActionReceiver
    {
        /// <summary>
        /// Parsed and validated action request ready for script-thread execution.
        /// </summary>
        public sealed class ActionRequest
        {
            public readonly int id;
            public readonly string action;
            public readonly float paramX;
            public readonly float paramY;

            public ActionRequest(int id, string action, float paramX, float paramY)
            {
                this.id = id;
                this.action = action;
                this.paramX = paramX;
                this.paramY = paramY;
            }
        }

        // Compiled-in whitelist mirror of ACTION_WHITELIST.md
        private static readonly HashSet<string> Whitelist = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        {
            "set_waypoint",
            "spawn_companion",
            "heal_player"
        };

        private const int MaxQueuedActions = 16;

        private readonly object queueLock = new object();
        private readonly Queue<ActionRequest> pendingActions = new Queue<ActionRequest>();

        /// <summary>Count of actions dropped because queue was full (script-thread read only).</summary>
        public int DroppedActions { get; private set; }

        /// <summary>
        /// Parse a raw JSON line from the brain. If it's a valid action request
        /// and passes the whitelist, enqueue it for the script thread.
        /// Returns true if the line was consumed as an action (even if refused),
        /// false if it's not an action line (caller should ignore it).
        /// The out parameter <paramref name="refuseAck"/> contains a pre-built
        /// nack line if the action was refused, or null otherwise.
        /// </summary>
        public bool ParseAndEnqueue(string rawLine, out string refuseAck)
        {
            refuseAck = null;

            if (string.IsNullOrEmpty(rawLine))
            {
                return false;
            }

            // Quick check: action lines must contain "type" and "action"
            if (rawLine.IndexOf("\"type\"", StringComparison.Ordinal) < 0 ||
                rawLine.IndexOf("\"action\"", StringComparison.Ordinal) < 0)
            {
                return false;
            }

            // Hand-parse the JSON to avoid adding a JSON dependency.
            // Expected: {"type":"action","id":<int>,"action":"<name>","params":{"x":<float>,"y":<float>}}
            int id;
            string actionName;
            float x, y;
            bool hasParams;

            if (!TryParseActionJson(rawLine, out id, out actionName, out x, out y, out hasParams))
            {
                return false;
            }

            // Whitelist check
            if (!Whitelist.Contains(actionName))
            {
                refuseAck = BuildAck(id, false, "action not whitelisted: " + actionName);
                Console.WriteLine("GtaCopilot: REFUSED action '" + actionName + "' (not whitelisted)");
                return true;
            }

            // set_waypoint requires coordinates — refuse rather than default to (0,0)
            if (string.Equals(actionName, "set_waypoint", StringComparison.OrdinalIgnoreCase) && !hasParams)
            {
                refuseAck = BuildAck(id, false, "set_waypoint requires params.x and params.y");
                Console.WriteLine("GtaCopilot: REFUSED set_waypoint id=" + id + " (missing params)");
                return true;
            }

            var request = new ActionRequest(id, actionName, x, y);

            lock (queueLock)
            {
                if (pendingActions.Count >= MaxQueuedActions)
                {
                    // Drop-newest per spec
                    DroppedActions++;
                    refuseAck = BuildAck(id, false, "action queue full");
                    Console.WriteLine("GtaCopilot: DROPPED action id=" + id + " (queue full)");
                    return true;
                }

                pendingActions.Enqueue(request);
            }

            Console.WriteLine("GtaCopilot: queued action id=" + id + " " + actionName +
                " x=" + x.ToString("F1", CultureInfo.InvariantCulture) +
                " y=" + y.ToString("F1", CultureInfo.InvariantCulture));

            return true;
        }

        /// <summary>
        /// Called from the script thread (OnTick). Returns the next action
        /// or null if the queue is empty.
        /// </summary>
        public ActionRequest TryDequeue()
        {
            lock (queueLock)
            {
                return pendingActions.Count > 0 ? pendingActions.Dequeue() : null;
            }
        }

        /// <summary>
        /// Build a JSON ack line to send back to the brain.
        /// </summary>
        public static string BuildAck(int id, bool ok, string err)
        {
            // Hand-rolled JSON: {"ack":<id>,"ok":true|false,"err":"<str>"|null}
            var sb = new StringBuilder(64);
            sb.Append("{\"ack\":");
            sb.Append(id.ToString(CultureInfo.InvariantCulture));
            sb.Append(",\"ok\":");
            sb.Append(ok ? "true" : "false");
            sb.Append(",\"err\":");
            if (err == null)
            {
                sb.Append("null");
            }
            else
            {
                sb.Append('"');
                // Minimal JSON escape for the error string
                for (int i = 0; i < err.Length; i++)
                {
                    char c = err[i];
                    if (c == '"') sb.Append("\\\"");
                    else if (c == '\\') sb.Append("\\\\");
                    else if (c < 0x20) sb.Append(' ');
                    else sb.Append(c);
                }
                sb.Append('"');
            }
            sb.Append('}');
            return sb.ToString();
        }

        // ------------------------------------------------------------------
        // Minimal hand-rolled JSON parser for the action wire format.
        // We only need to extract: id (int), action (string), params.x, params.y
        // ------------------------------------------------------------------

        private static bool TryParseActionJson(string json, out int id, out string action, out float x, out float y, out bool hasParams)
        {
            id = 0;
            action = null;
            x = 0;
            y = 0;
            hasParams = false;

            // Verify it's an "action" type
            string typeValue = ExtractStringValue(json, "type");
            if (typeValue != "action")
            {
                return false;
            }

            // Extract id
            string idStr = ExtractNumericValue(json, "id");
            if (idStr == null || !int.TryParse(idStr, NumberStyles.Integer, CultureInfo.InvariantCulture, out id))
            {
                return false;
            }

            // Extract action name
            action = ExtractStringValue(json, "action");
            if (string.IsNullOrEmpty(action))
            {
                return false;
            }

            // Extract params.x and params.y
            int paramsIdx = json.IndexOf("\"params\"", StringComparison.Ordinal);
            if (paramsIdx < 0)
            {
                // Some actions have no params (heal_player, spawn_companion)
                return true;
            }

            string paramsSection = json.Substring(paramsIdx);

            string xStr = ExtractNumericValue(paramsSection, "x");
            string yStr = ExtractNumericValue(paramsSection, "y");

            bool gotX = false, gotY = false;

            if (xStr != null)
            {
                gotX = float.TryParse(xStr, NumberStyles.Float, CultureInfo.InvariantCulture, out x);
            }
            if (yStr != null)
            {
                gotY = float.TryParse(yStr, NumberStyles.Float, CultureInfo.InvariantCulture, out y);
            }

            hasParams = gotX && gotY;
            return true;
        }

        /// <summary>Extract a string value for a given key like "type" → finds "type":"value"</summary>
        private static string ExtractStringValue(string json, string key)
        {
            string pattern = "\"" + key + "\":";
            int keyIdx = json.IndexOf(pattern, StringComparison.Ordinal);
            if (keyIdx < 0) return null;

            int quoteStart = json.IndexOf('"', keyIdx + pattern.Length);
            if (quoteStart < 0) return null;

            int quoteEnd = json.IndexOf('"', quoteStart + 1);
            if (quoteEnd < 0) return null;

            return json.Substring(quoteStart + 1, quoteEnd - quoteStart - 1);
        }

        /// <summary>Extract a numeric value for a given key like "id"</summary>
        private static string ExtractNumericValue(string json, string key)
        {
            string pattern = "\"" + key + "\":";
            int keyIdx = json.IndexOf(pattern, StringComparison.Ordinal);
            if (keyIdx < 0) return null;

            int numStart = keyIdx + pattern.Length;
            while (numStart < json.Length && (json[numStart] == ' ' || json[numStart] == '\t'))
            {
                numStart++;
            }

            int numEnd = numStart;
            while (numEnd < json.Length &&
                   (char.IsDigit(json[numEnd]) || json[numEnd] == '-' || json[numEnd] == '.' || json[numEnd] == 'e' || json[numEnd] == 'E' || json[numEnd] == '+'))
            {
                numEnd++;
            }

            if (numEnd == numStart) return null;

            return json.Substring(numStart, numEnd - numStart);
        }
    }
}
