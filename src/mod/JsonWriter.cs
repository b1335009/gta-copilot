using System.Globalization;
using System.Text;

namespace GtaCopilot.Mod
{
    /// <summary>
    /// Minimal hand-rolled JSON writer for the exact Phase 1 schema. No JSON
    /// package dependency is used so deployment stays as a single mod assembly.
    /// </summary>
    public static class JsonWriter
    {
        public static string Write(GameState state)
        {
            StringBuilder builder = new StringBuilder(192);

            builder.Append('{');
            AppendPropertyName(builder, "t");
            builder.Append(state.t.ToString(CultureInfo.InvariantCulture));
            builder.Append(',');

            AppendPropertyName(builder, "health");
            builder.Append(state.health.ToString(CultureInfo.InvariantCulture));
            builder.Append(',');

            AppendPropertyName(builder, "max_health");
            builder.Append(state.max_health.ToString(CultureInfo.InvariantCulture));
            builder.Append(',');

            AppendPropertyName(builder, "armor");
            builder.Append(state.armor.ToString(CultureInfo.InvariantCulture));
            builder.Append(',');

            AppendPropertyName(builder, "wanted");
            builder.Append(state.wanted.ToString(CultureInfo.InvariantCulture));
            builder.Append(',');

            AppendPropertyName(builder, "pos");
            AppendPosition(builder, state.pos);
            builder.Append(',');

            AppendPropertyName(builder, "vehicle");
            AppendVehicle(builder, state.vehicle);
            builder.Append(',');

            AppendPropertyName(builder, "companion");
            AppendCompanion(builder, state.companion);
            builder.Append('}');

            return builder.ToString();
        }

        private static void AppendCompanion(StringBuilder builder, GameState.CompanionState companion)
        {
            if (companion == null)
            {
                builder.Append("null");
                return;
            }

            builder.Append('{');
            AppendPropertyName(builder, "health");
            builder.Append(companion.health.ToString(CultureInfo.InvariantCulture));
            builder.Append(',');
            AppendPropertyName(builder, "dead");
            builder.Append(companion.dead ? "true" : "false");
            builder.Append('}');
        }

        private static void AppendPosition(StringBuilder builder, GameState.PositionState position)
        {
            GameState.PositionState safePosition = position ?? new GameState.PositionState(0.0f, 0.0f, 0.0f);

            builder.Append('{');
            AppendPropertyName(builder, "x");
            builder.Append(safePosition.x.ToString("F1", CultureInfo.InvariantCulture));
            builder.Append(',');
            AppendPropertyName(builder, "y");
            builder.Append(safePosition.y.ToString("F1", CultureInfo.InvariantCulture));
            builder.Append(',');
            AppendPropertyName(builder, "z");
            builder.Append(safePosition.z.ToString("F1", CultureInfo.InvariantCulture));
            builder.Append('}');
        }

        private static void AppendVehicle(StringBuilder builder, GameState.VehicleState vehicle)
        {
            if (vehicle == null)
            {
                builder.Append("null");
                return;
            }

            builder.Append('{');
            AppendPropertyName(builder, "name");
            AppendString(builder, vehicle.name);
            builder.Append(',');
            AppendPropertyName(builder, "speed_kmh");
            builder.Append(vehicle.speed_kmh.ToString("F0", CultureInfo.InvariantCulture));
            builder.Append('}');
        }

        private static void AppendPropertyName(StringBuilder builder, string name)
        {
            AppendString(builder, name);
            builder.Append(':');
        }

        private static void AppendString(StringBuilder builder, string value)
        {
            builder.Append('"');
            AppendEscapedStringBody(builder, value ?? string.Empty);
            builder.Append('"');
        }

        private static void AppendEscapedStringBody(StringBuilder builder, string value)
        {
            for (int i = 0; i < value.Length; i++)
            {
                char c = value[i];
                switch (c)
                {
                    case '"':
                        builder.Append("\\\"");
                        break;
                    case '\\':
                        builder.Append("\\\\");
                        break;
                    case '\b':
                        builder.Append("\\b");
                        break;
                    case '\f':
                        builder.Append("\\f");
                        break;
                    case '\n':
                        builder.Append("\\n");
                        break;
                    case '\r':
                        builder.Append("\\r");
                        break;
                    case '\t':
                        builder.Append("\\t");
                        break;
                    default:
                        if (c < 0x20)
                        {
                            builder.Append("\\u");
                            builder.Append(((int)c).ToString("x4", CultureInfo.InvariantCulture));
                        }
                        else
                        {
                            builder.Append(c);
                        }
                        break;
                }
            }
        }
    }
}
