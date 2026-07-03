namespace GtaCopilot.Mod
{
    /// <summary>
    /// Plain Phase 1 state container. Field names intentionally mirror the JSON
    /// schema keys so serializer output stays obvious and dependency-free.
    /// </summary>
    public sealed class GameState
    {
        public readonly long t;
        public readonly int health;
        public readonly int max_health;
        public readonly int armor;
        public readonly int wanted;
        public readonly PositionState pos;
        public readonly VehicleState vehicle;

        public GameState(
            long t,
            int health,
            int maxHealth,
            int armor,
            int wanted,
            PositionState pos,
            VehicleState vehicle)
        {
            this.t = t;
            this.health = health;
            this.max_health = maxHealth;
            this.armor = armor;
            this.wanted = wanted;
            this.pos = pos;
            this.vehicle = vehicle;
        }

        /// <summary>
        /// Compares observed game data for change-detection. The timestamp is
        /// intentionally ignored; time-only emissions are handled by heartbeat.
        /// </summary>
        public bool HasSameObservedValues(GameState other)
        {
            if (other == null)
            {
                return false;
            }

            if (health != other.health ||
                max_health != other.max_health ||
                armor != other.armor ||
                wanted != other.wanted)
            {
                return false;
            }

            if (pos == null)
            {
                if (other.pos != null)
                {
                    return false;
                }
            }
            else if (!pos.HasSameValues(other.pos))
            {
                return false;
            }

            if (vehicle == null)
            {
                return other.vehicle == null;
            }

            return vehicle.HasSameValues(other.vehicle);
        }

        public sealed class PositionState
        {
            public readonly float x;
            public readonly float y;
            public readonly float z;

            public PositionState(float x, float y, float z)
            {
                this.x = x;
                this.y = y;
                this.z = z;
            }

            public bool HasSameValues(PositionState other)
            {
                return other != null && x == other.x && y == other.y && z == other.z;
            }
        }

        public sealed class VehicleState
        {
            public readonly string name;
            public readonly float speed_kmh;

            public VehicleState(string name, float speedKmh)
            {
                this.name = name ?? string.Empty;
                this.speed_kmh = speedKmh;
            }

            public bool HasSameValues(VehicleState other)
            {
                return other != null && name == other.name && speed_kmh == other.speed_kmh;
            }
        }
    }
}
