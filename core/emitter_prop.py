######
#
# Emitter Prop object type V1.0 by Elvaerwyn MH_2 2026
# holding also particles to work as a unit
# For use in the prop panel plugin for Makehuman 2
#
######

import random
import time

class MH2LiveEmitterProp:
    def __init__(self, prop_id, raw_json_data):
        """
        Initializes an explicit Emitter Prop by map-matching 
        the raw attributes directly out of your JSON file.
        """
        self.prop_id = prop_id
        print ("emitter init", prop_id)
        # Raw Data Parameter Mapping Match
        self.name = raw_json_data.get("name", "Unnamed Emitter")
        self.mesh_path = raw_json_data.get("mesh_path", "")
        self.is_mesh_visible = raw_json_data.get("is_mesh_visible", True)
        self.max_particles = raw_json_data.get("particle_count", 300)
        self.particle_color = raw_json_data.get("particle_color", [1.0, 1.0, 1.0, 1.0])
        self.default_bone = raw_json_data.get("default_bone", "hand_R")
        
        # Running Architecture Parameters
        self.state = 'holding'  # holding, placed, arranged, used
        self.world_position = [0.0, 0.0, 0.0]
        self.world_matrix = None # Assigned dynamically by viewport steps
        self.mesh_buffers = None  # Populated when an .obj is actively drawn
        
        # Simulation Allocations
        self.particles_pool = []    # TODO: not sure if both are needed
        self.particles = []



class MH2PropParticle:
    """A single particle dot spawned by an emitter prop."""
    def __init__(self, origin_pos, color=None):
        self.x = float(origin_pos[0])
        self.y = float(origin_pos[1])
        self.z = float(origin_pos[2])
        self.vx = random.uniform(-0.3, 0.3)
        self.vy = random.uniform(1.2, 2.5)
        self.vz = random.uniform(-0.3, 0.3)

        # Safely extracts color properties from color, color_rgba, or particle_color
        raw_color = color
        if hasattr(color, 'color_rgba'):
            raw_color = color.color_rgba
        elif hasattr(color, 'particle_color'):
            raw_color = color.particle_color

        if isinstance(raw_color, (list, tuple)) and len(raw_color) >= 3:
            self.color = [float(c) for c in raw_color[:4]]
            if len(self.color) == 3:
                self.color.append(1.0) # Automatically inject fully opaque alpha target
        else:
            self.color = [1.0, 0.4, 0.0, 1.0] # Fire Magic Torch vibrant orange fallback

        self.lifetime = 0.0
        self.lifespan = random.uniform(0.6, 1.5)

    def is_dead(self):
        return self.lifetime > self.lifespan

    def update(self, span):
        self.lifetime += span
        self.x += self.vx * span  # X Axis translates outward
        self.y += self.vy * span  # Y Axis RISES UPWARD
        self.z += self.vz * span  # Z Axis translates outward

        # Apply stable gravity downward velocity pull strictly onto the Y axis channel vector
        self.vy -= 2.5 * span

