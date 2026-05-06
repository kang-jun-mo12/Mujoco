import mujoco
import gymnasium as gym
import numpy as np

print(f"MuJoCo version: {mujoco.__version__}")
print(f"Gymnasium version: {gym.__version__}")
print(f"NumPy version: {np.__version__}")

# Basic MuJoCo model test
xml = """
<mujoco>
  <worldbody>
    <body name="box" pos="0 0 1">
      <freejoint/>
      <geom type="box" size="0.1 0.1 0.1" rgba="1 0 0 1"/>
    </body>
  </worldbody>
</mujoco>
"""

model = mujoco.MjModel.from_xml_string(xml)
data = mujoco.MjData(model)
mujoco.mj_step(model, data)
print(f"\nMuJoCo model test passed. Box position after step: {data.qpos[:3]}")

# Gymnasium MuJoCo env test
env = gym.make("HalfCheetah-v5")
obs, info = env.reset()
print(f"\nGymnasium HalfCheetah-v5:")
print(f"  Observation shape: {obs.shape}")
print(f"  Action space: {env.action_space}")
env.close()

print("\nAll tests passed!")
