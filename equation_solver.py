from math import pi, sin, radians

SLING_MASS             = 1.5          # mass of the sling, in kg

# Band Properties
BAND_STRENGTH          = 4.4482 * ((14.3 + (21.3 / 2)) / 2)  # strength of a single rubber band, in Newtons
BAND_REST_LENGTH       = 0.254        # resting (unstretched) length of the bands, in meters

# Launch conditions
LAUNCH_ANGLE           = radians(45)  # launch angle (entered in degrees, converted to radians)
GRAVITY                = 9.81         # acceleration due to gravity, in m/s^2
DRAG_COEFFICIENT       = 0.55         # drag coefficient of the pumpkin
AIR_DENSITY            = 1.21         # air density in Rochester, in kg/m^3
PUMPKIN_DENSITY        = 800          # average density of a pumpkin, in kg/m^3
                                      #  (== 800 g/L == 0.8 g/cm^3)

pumpkin_mass           = 0.9          # mass of the pumpkin
efficiency             = 0.8          # fraction of ideal band force that reaches the pumpkin
band_count             = 4 * 6        # total number of bands
target_range           = 300          # desired range, in feet

newton_to_pound_force  = 0.2248       # unit conversion: 1 N = 0.2248 lbf

target_range_converted = target_range * 0.3048 # Target range converted from feet to meters


def cross_sectional_area():
    # Cross-sectional area of the pumpkin, modeled as a sphere: A = pi * r^2
    area = ((((3 * (pumpkin_mass / PUMPKIN_DENSITY)) / (4 * pi)) ** (1/3)) ** 2) * pi
    return area


def drag_velocity_scale():
    # Drag velocity scale: Q = sqrt( 2 m g / (rho * A * C_d) )
    # uses pumpkin_mass alone: only the pumpkin flies, the sling does not
    scale = ((2 * pumpkin_mass * GRAVITY) / (AIR_DENSITY * cross_sectional_area() * DRAG_COEFFICIENT)) ** 0.5
    return scale


def vacuum_initial_velocity():
    # Initial velocity ignoring air drag: v = sqrt( R g / sin(2 theta) )
    velocity = ((target_range_converted * GRAVITY) / sin(2 * LAUNCH_ANGLE)) ** 0.5
    return velocity


def initial_velocity():
    # Initial velocity required once quadratic drag is included
    velocity = (((target_range_converted * GRAVITY) / sin(2 * LAUNCH_ANGLE)) * (1 + ((4 * vacuum_initial_velocity() * sin(LAUNCH_ANGLE)) / (3 * drag_velocity_scale())))) ** 0.5
    return velocity


def launched_mass():
    # everything the bands have to accelerate: the pumpkin plus the sling
    mass = pumpkin_mass + SLING_MASS
    return mass


def elongation_factor():
    # Band elongation factor: sqrt( mass / stiffness ), where stiffness = BAND_STRENGTH * band_count / BAND_REST_LENGTH
    # mass is launched_mass(): the sling rides with the pumpkin and loads the bands too
    stiffness = BAND_STRENGTH * band_count / BAND_REST_LENGTH
    factor = (launched_mass() / (efficiency * stiffness)) ** 0.5
    return factor


def draw_distance():
    # Draw distance (elongation distance): d = E_L * v_0
    return elongation_factor() * initial_velocity()


def stretch_ratio():
    # Stretch ratio: S_r = d / L_0
    return draw_distance() / BAND_REST_LENGTH


def launch_force():
    # Final launch force, converted from Newtons to pounds-force
    velocity = initial_velocity()
    force = newton_to_pound_force * ((launched_mass() * (velocity ** 2)) / (efficiency * draw_distance()))
    return force


if __name__ == "__main__":
    print(launch_force())
