######
#
# Emitter Prop object type V1.1 by Elvaerwyn MH_2 2026
# For use in the prop panel plugin for Makehuman 2
#
######

import random
import time
import os
import numpy as np

from PySide6.QtGui import QVector3D
from OpenGL import GL as gl

# MH2 specific
#
from core.debug import dumper
from obj3d.object3d import object3d
from opengl.buffers import OpenGlBuffers, RenderedObject
from opengl.texture import MH_Texture

class MH2LiveEmitterProp:
    def __init__(self, glob, prop_id, raw_json_data):
        """
        Initializes an explicit Emitter Prop by map-matching 
        the raw attributes directly out of your JSON file.
        """
        self.glob = glob        # to have access to render-Engine etc.
        self.prop_id = prop_id
        self.light = self.glob.openGLWindow.light
        if raw_json_data is None:
            raw_json_data = {}
            
        self.name = raw_json_data.get("name", "Unnamed Emitter")
        self.mesh_path = raw_json_data.get("mesh_path", "")
        self.emitter_obj_path = raw_json_data.get("emitter_object", None)
        self.is_mesh_visible = raw_json_data.get("is_mesh_visible", True)
        self.max_particles = raw_json_data.get("particle_count", 300)
        self.parented = raw_json_data.get("use_parenting", False)

        self.particle_color = raw_json_data.get("color_rgba", raw_json_data.get("particle_color", [1.0, 0.3, 1.0, 1.0]))
        self.a = float(self.particle_color[3]) if len(self.particle_color) >= 4 else 1.0
        self.r, self.g, self.b = float(self.particle_color[0]), float(self.particle_color[1]), float(self.particle_color[2])

        self.default_bone = raw_json_data.get("default_bone", "hand_R")
        
        # New Explicit Emitter Type Gate Parameter Target Link:
        # OPTIONS: "PARTICLES", "SPRITES", "TEXTURED_SPRITES", "PHYSICAL_MESH"
        self.emitter_mode = raw_json_data.get("emitter_mode", "PARTICLES").upper().strip()
        self.particle_texture = raw_json_data.get("particle_texture", "PLAIN")
        self.particle_draw_size = float(raw_json_data.get("particle_draw_size", 6.0))

        print("emitter init", prop_id, "mode", self.emitter_mode)
        
        # Running Architecture Parameters
        self.state = 'holding'  # holding, placed, arranged, used
        self.world_position = [0.0, 0.0, 0.0]
        self.world_matrix = None 

        # variables for textures
        #
        self.texture = None

        # variables for meshes
        #
        self.obj = None             # object3d object
        self.mesh_buffers = None    # openGL buffer object for particles (not emitter itself)
                                    # can be extended to a list in case of more then one buffer is needed
        self.render = None          # rendered object
        
        # Simulation Memory Allocations
        self.particles_pool = []    
        self.particles = []

    def loadParticleMesh(self, path=None):
        """
        load the particle mesh, extra not in init to keep control (return values is False, when sth. is not okay,
        init would fail. Only loads mesh when mode is PHYSICAL_MESH, but returns True (okay) in this case.
        :param path: alternative path (will replace mesh self.meshpath if not None
        """
        if self.emitter_mode != "PHYSICAL_MESH":
            return True, "No mesh"

        if path is not None:
            self.emitter_obj_path = path

        self.obj = object3d(self.glob, None, "props")
        (success, err) = self.obj.load(self.emitter_obj_path, True)
        if not success:
            return False, err

        self.obj.initMaterial() # init that empty

        self.mesh_buffers = OpenGlBuffers()
        self.mesh_buffers.GetBuffers(self.obj.gl_coord, self.obj.gl_norm, self.obj.gl_uvcoord)
        self.render = RenderedObject(self.glob.openGLWindow, self.obj, None, self.mesh_buffers)
        return True, "okay"

    def loadParticleTexture(self):
        if self.emitter_mode != "TEXTURED_SPRITES":
            return True
        name = os.path.join(self.glob.env.path_sys, self.particle_texture) # TODO: best would be props without data
        print ("load", name)
        texture = MH_Texture(self.glob)
        self.texture = texture.load(name)
        if self.texture is None:
            self.emitter_mode = "PARTICLES"
        return self.texture

    def drawMesh(self, proj_view_matrix, campos):
        for p in self.particles_pool:
            self.render.setPosition(QVector3D(p.x, p.y, p.z))
            self.render.setScale(QVector3D(p.scale[0], p.scale[1], p.scale[2]))
            self.render.setXRotation(p.rotation[0])
            self.render.setYRotation(p.rotation[1])
            self.render.setZRotation(p.rotation[2])

            self.render.draw(proj_view_matrix, campos, self.light, False)

    def newParticles(self, cnt):
        for _ in range(cnt):
            self.particles_pool.append(MH2PropParticle(self))

    def flushDead(self):
        self.particles_pool = [p for p in self.particles_pool if not p.is_dead()]

    def poolCopy(self):
        self.particles = [[float(part.x), float(part.y), float(part.z)] for part in self.particles_pool]
        self.particles = np.ascontiguousarray(self.particles, dtype=np.float32)


    def getBonePosition(self):
        """
        TODO: it would be better to not put the evaluation here, but the parent object still stay in place
              while animation
        """
        bc = self.glob.baseClass
        coord, bone  = bc.getVirtualBonePosition(self.default_bone)
        if bone is not None:
            return coord

        """
        if bc.in_posemode:
           b_rot = getattr(bone, 'matPoseVerts', None)
        else:
           b_rot = getattr(bone, 'matRestGlobal', None)
        """
        return self.world_position # fallback

    def loop(self, new, progress):
        # 1. Generate fresh particle records up to the assigned buffer threshold
        if len(self.particles_pool) < int(self.max_particles):
            if self.parented:
                self.world_position = self.getBonePosition()

            self.newParticles(new)

        # 2. Progress coordinates smoothly using a flat physics delta time step
        for p in self.particles_pool:
            p.update(progress)          # Progress physics forward using 30fps step

        # 3. Flush expired particle nodes out of active drawing tracking lists
        self.flushDead()

        # 4. Bind values cleanly onto the shared object so opengl/multi_prop.py can read them
        self.poolCopy()

    def startOpenGL(self):
        gl.glPushMatrix()
        gl.glPushAttrib(gl.GL_POINT_BIT | gl.GL_CURRENT_BIT | gl.GL_ENABLE_BIT | gl.GL_TEXTURE_BIT)
        gl.glDisable(gl.GL_LIGHTING)

        if hasattr(self, 'runtime_gl_matrix') and self.runtime_gl_matrix is not None:
            gl.glEnable(gl.GL_NORMALIZE)
            gl.glMultMatrixf(prop.runtime_gl_matrix)

    def finishOpenGL(self):
        gl.glEnableClientState(gl.GL_VERTEX_ARRAY)
        gl.glVertexPointer(3, gl.GL_FLOAT, 0, self.particles)
        gl.glDrawArrays(gl.GL_POINTS, 0, len(self.particles) // 3)

        gl.glDisableClientState(gl.GL_VERTEX_ARRAY)
        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
        gl.glPopAttrib()
        gl.glPopMatrix()

    def drawDustParticles(self):
        self.startOpenGL()
        gl.glDisable(gl.GL_TEXTURE_2D)
        gl.glDisable(gl.GL_POINT_SPRITE)
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        gl.glPointSize(self.particle_draw_size)
        self.finishOpenGL()

    def drawSprites(self):
        self.startOpenGL()
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        gl.glDisable(gl.GL_TEXTURE_2D)
        gl.glEnable(gl.GL_POINT_SPRITE)
        gl.glTexEnvi(gl.GL_POINT_SPRITE, gl.GL_COORD_REPLACE, gl.GL_TRUE)
        gl.glPointSize(self.particle_draw_size if self.particle_draw_size > 6.0 else 16.0)
        gl.glColor4f(self.r, self.g, self.b, self.a)
        self.finishOpenGL()

    def drawTexSprites(self):
        self.startOpenGL()
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE) # Realistic additive blending
        gl.glEnable(gl.GL_POINT_SPRITE)
        gl.glTexEnvi(gl.GL_POINT_SPRITE, gl.GL_COORD_REPLACE, gl.GL_TRUE)
        gl.glEnable(gl.GL_TEXTURE_2D)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        self.texture.bind()
        gl.glPointSize(self.particle_draw_size if self.particle_draw_size > 6.0 else 48.0)
        gl.glColor4f(1.0, 1.0, 1.0, 1.0)
        self.finishOpenGL()



class MH2PropParticle:
    """A single particle element spawned by an emitter prop module."""
    def __init__(self, emitter):
        self.x, self.y, self.z = emitter.world_position
        self.color = emitter.particle_color     # correctly formed already
        
        # Random vector dispersion trajectory calculation assignments
        self.vx = random.uniform(-0.6, 0.6)
        self.vy = random.uniform(4.6, 10.0)
        self.vz = random.uniform(-0.6, 0.6)

        # Retain independent transformations matrix for physical mesh instancing copies
        self.rotation = [random.uniform(0, 360), random.uniform(0, 360), random.uniform(0, 360)]
        self.scale = [0.1, 0.1, 0.1]

        self.lifetime = 0.0
        self.lifespan = random.uniform(0.6, 1.5)

    def is_dead(self):
        return self.lifetime > self.lifespan

    def update(self, span):
        self.lifetime += span
        self.x += self.vx * span  
        self.y += self.vy * span  
        self.z += self.vz * span  
        
        # Apply stable down-axis gravity velocity pull calculations over time frames
        self.vy -= 2.5 * span

