using System;
using GTA;
using GTA.Math;

namespace GtaCopilot.Mod
{
    /// <summary>
    /// Reads GTA/SHVDN state for Phase 1. Call this only from Script.OnTick on
    /// the SHVDN script thread; it intentionally performs native-backed reads
    /// synchronously and does not use timers, tasks, or worker threads.
    /// </summary>
    public sealed class GameStateReader
    {
        private static readonly DateTime UnixEpoch = new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc);
        private const float MetersPerSecondToKilometersPerHour = 3.6f;

        public GameState Read()
        {
            Player player = Game.Player;
            Ped ped = player == null ? null : player.Character;

            if (ped == null)
            {
                return new GameState(
                    CurrentUnixMilliseconds(),
                    0,
                    0,
                    0,
                    player == null ? 0 : player.WantedLevel,
                    new GameState.PositionState(0.0f, 0.0f, 0.0f),
                    null);
            }

            Vector3 position = ped.Position;
            GameState.VehicleState vehicle = ReadVehicle(ped);

            return new GameState(
                CurrentUnixMilliseconds(),
                ped.Health,
                ped.MaxHealth,
                ped.Armor,
                player.WantedLevel,
                new GameState.PositionState(
                    RoundToTenths(position.X),
                    RoundToTenths(position.Y),
                    RoundToTenths(position.Z)),
                vehicle);
        }

        private static GameState.VehicleState ReadVehicle(Ped ped)
        {
            if (!ped.IsInVehicle())
            {
                return null;
            }

            Vehicle vehicle = ped.CurrentVehicle;
            if (vehicle == null)
            {
                return null;
            }

            string name = ResolveVehicleName(vehicle);
            float speedKmh = RoundToOnes(vehicle.Speed * MetersPerSecondToKilometersPerHour);
            return new GameState.VehicleState(name, speedKmh);
        }

        private static string ResolveVehicleName(Vehicle vehicle)
        {
            string displayName = vehicle.DisplayName;
            if (string.IsNullOrEmpty(displayName))
            {
                return string.Empty;
            }

            string localizedName = Game.GetLocalizedString(displayName);
            if (IsUsableDisplayName(localizedName))
            {
                return localizedName;
            }

            return displayName;
        }

        private static bool IsUsableDisplayName(string value)
        {
            return !string.IsNullOrEmpty(value) && value != "NULL" && value != "CARNOTFOUND";
        }

        private static long CurrentUnixMilliseconds()
        {
            return (long)(DateTime.UtcNow - UnixEpoch).TotalMilliseconds;
        }

        private static float RoundToTenths(float value)
        {
            return NormalizeZero((float)Math.Round(value, 1, MidpointRounding.AwayFromZero));
        }

        private static float RoundToOnes(float value)
        {
            return NormalizeZero((float)Math.Round(value, 0, MidpointRounding.AwayFromZero));
        }

        private static float NormalizeZero(float value)
        {
            return value == 0.0f ? 0.0f : value;
        }
    }
}
