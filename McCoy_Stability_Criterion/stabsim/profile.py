import numpy as np
from scipy import integrate
from .utility import read_csv

"""
Simulates a spin-stabilized launch profile
"""
class Profile:
    def __init__(self, rocket, motor, init_spin, length=0, motor_pos=0, hangle=0, timesteps=50):
        self.rocket = read_csv(rocket)
        self.motor = motor
        self.init_spin = init_spin
        self.length = length
        # assume a length==0 implies simulation should end at end of motor burn
        if self.length == 0:
            self.length = self.motor.burn_time
        self.motor_pos = motor_pos

        # thrust is set to polynomial fit to get equally spaced timesteps for subsequent calcs
        t = np.linspace(0, self.motor.burn_time, len(self.motor.thrust))
        # TODO: double check with prop that polynomial fit is sufficient and ask abt degree
        thrust = np.polyfit(t, self.motor.thrust, 4)
        force = np.poly1d(thrust) # TODO: subtract the drag and gravity

        # simple integration and Newton's second
        self.tt = np.linspace(0, self.length, timesteps)
        # Mass calcuations over time
        self.mass = np.array([self.motor.mass(t) + self.rocket["Mass"] for t in self.tt])
        self.accel = np.array([force(t) / (self.motor.mass(t) + self.rocket["Mass"]) \
            for t in self.tt])
        vel = np.array(integrate.cumtrapz(self.accel, x=self.tt, initial=0))
        self.vel = vel 
        self.altit = np.array(integrate.cumtrapz(vel * np.cos(hangle), x=self.tt, initial=0))

    def rho(self):
        rho = []
        trop_x = np.argmax(self.altit > 11000)
        if trop_x == 0:
            trop_x = len(self.altit)
        rho.extend([1.225 * (288.15 / (288.15 + -0.0065 * x ** (1 + (9.8 * 0.02896) / (8.3145 * -0.0065)))) \
            for x in self.altit[:trop_x]])

        strat_x = np.argmax(self.altit > 20000)
        if strat_x == 0:
            strat_x = len(self.altit)
        rho.extend([0.364 * np.exp(-(9.8 * 0.02896 * x / (8.3145 * 216.65))) \
            for x in self.altit[trop_x:strat_x]])

        # assumed below the mesosphere (32km)
        rho.extend([0.088 * (216.65 / (216.65 + 0.001 * x ** (1 + (9.8 * 0.02896) / (8.3145 * 0.001)))) \
            for x in self.altit[trop_x:strat_x]])

        return np.array(rho)

    def iz(self):
        return np.array([self.rocket["I_z"] + self.motor.iz(time) + self.motor.mass(time) * self.motor_pos**2 \
            for time in self.tt])

    def ix(self):
        return np.array([self.rocket["I_x"] + self.motor.ix(time) + self.motor.mass(time) * self.motor_pos**2 \
            for time in self.tt])

    def gyro_stab_crit(self):
        # TODO: the number of calipers also changes as motor burns and CG changes, add fcn for this too
        return self.vel / self.iz() * np.sqrt(2 * self.rho() * self.ix() * self.rocket['Surface Area'] * \
            self.rocket['Calipers'] * self.rocket['Diameter']) 

    def dynamic_stab_crit(self):
        # McCoy dynamics stability criterion in radians per second
        # TODO: fill in values for coefficients
        cm_alpha = # Pitching/rolling moment coeff
        cl_alpha = # Lift force coeff
        cd = # Drag coeff
        cm_q = # Pitch damping moment due to transverse angular velocity
        cm_alpha_dot = # Pitch damping moment coeff due to rate of change of angle of attack
        cm_p_alpha = # Magnus moment coeff
        return self.vel * np.sqrt(2 * self.rho() * self.rocket['Surface Area'] * self.rocket['Diameter'] * cm_alpha * self.ix()) * \
            (cl_alpha - cd - (self.mass * self.rocket['Diameter'] ** 2 / self.ix()) * (cm_q + cm_alpha_dot)) / \
                (2 * (self.iz() * cl_alpha + self.mass * self.rocket['Diameter'] ** 2 * cm_p_alpha))

    def spin(self):
        # TODO: incorporate spin damping moment
        # air density changes with altitude (it changes with season and temp too)
        # using this model for now https://www.grc.nasa.gov/www/k-12/airplane/atmosmet.html
        density = []

        for altitude in self.altit:
            if altitude < 11000:
                temperature = 15.04 - .00649 * altitude
                pressure = 101.29 * ((temperature + 273.1) / 288.08) ** 5.256
            else if altitude >= 11000 and altitude < 25000:
                temperature = -56.46
                pressure = 22.65 * (2.718281828459045) ** (1.73 - .000157 * altitude)
            else:
                temperature = -131.21 + .00299 * altitude
                pressure = 2.488 * ((temperature + 273.1) / 216.6) ** -11.388
            density.append(pressure / (.2869 * (temperature + 273.1)))

        
        self.spin = [self.init_spin]
        self.damping = []
        #inertia gotten by adding component parts
        inertia = np.add(ix(self), iz(self))
        time = self.length / timesteps
        #coefficient using https://www.hindawi.com/journals/ijae/2020/6043721/ approximated to -.013
        
        for i in range (0, timesteps, 1):
            damping.append(.5 * density[i] * vel[i] * (self.rocket['Diameter'] ** 2) * self.rocket['Surface Area'] * self.spin[i] * -.013)
            angAccel = damping[i] / inertia
            spin.append(spin[i] + angAccel * time)            

        return self.spin
    def is_stable(self):
        return self.stab_crit() < self.spin()

    def min_spin(self):
        # TODO: incorporate skin drag despin
        return np.max(self.stab_crit())