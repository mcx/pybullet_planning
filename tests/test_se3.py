import pytest
import numpy as np
from numpy import linalg as LA

from pybullet_planning import connect, disconnect, wait_for_user, create_box, dump_body, get_link_pose, \
    euler_from_quat, RED, set_camera_pose, create_flying_body, create_shape, get_cylinder_geometry, \
    BLUE, get_movable_joints, get_links, SE3, set_joint_positions, \
    plan_joint_motion, add_line, GREEN, wait_if_gui, create_cylinder, set_pose, apply_alpha, interval_generator, \
    Pose, Euler, multiply, interpolate_poses, draw_pose, get_pose, remove_all_debug, intrinsic_euler_from_quat, \
    quat_from_euler

@pytest.fixture()
def parameters():
    size = 1.
    custom_limits = {
        'x': (-size, size),
        'y': (-size, size),
        'z': (-size, size),
    }
    return size, custom_limits

def get_delta_pose_generator(epsilon=0.1, angle=np.pi/6):
    lower = [-epsilon]*3 + [-angle]*3
    upper = [epsilon]*3 + [angle]*3
    for [x, y, z, roll, pitch, yaw] in interval_generator(lower, upper): # halton?
        pose = Pose(point=[x,y,z], euler=Euler(roll=roll, pitch=pitch, yaw=yaw))
        yield pose

def get_path_gen_fn(pos_step_size=0.002, ori_step_size=np.pi/18):
    pose_gen = get_delta_pose_generator()
    def gen_fn(pose):
        delta_pose = next(pose_gen)
        offset_pose = multiply(pose, delta_pose)
        yield interpolate_poses(offset_pose, pose, pos_step_size=pos_step_size, ori_step_size=ori_step_size)
    return gen_fn

@pytest.mark.flying_body
def test_flying_body(viewer):
    radius = 0.003
    height = 0.1
    connect(use_gui=viewer)
    set_camera_pose(camera_point=0.02*np.array([11., -1., 1.]))
    body = create_cylinder(radius=radius, height=height, color=apply_alpha(GREEN, 1))
    collision_id, visual_id = create_shape(get_cylinder_geometry(radius=radius, height=height), color=apply_alpha(BLUE, 1))
    robot = create_flying_body(SE3, collision_id, visual_id)

    body_link = get_links(robot)[-1]
    joints = get_movable_joints(robot)

    path_gen_fn = get_path_gen_fn()
    for i in range(3):
        print('Attempt: ', i)
        pose = get_pose(body)
        poses = next(path_gen_fn(pose))
        remove_all_debug()
        for p in poses:
            point, quat = p
            euler = intrinsic_euler_from_quat(quat)
            conf = np.concatenate([np.array(point), np.array(euler)])
            set_joint_positions(robot, joints, conf)
            set_pose(body, p)
            # draw_pose(p, length=0.1)

            link_pose = get_link_pose(robot, body_link)
            # draw_pose(link_pose, length=0.1)
            assert LA.norm(np.array(point) - np.array(link_pose[0])) < 1e-6
            assert LA.norm(np.array(quat) - np.array(link_pose[1])) < 1e-6
            wait_if_gui()
    wait_if_gui('Finish?')
    disconnect()

@pytest.mark.se3_motion_plan
def test_se3_planning(viewer, parameters):
    group = SE3
    SIZE, CUSTOM_LIMITS = parameters

    connect(use_gui=viewer)
    set_camera_pose(camera_point=SIZE*np.array([1., -1., 1.]))
    # TODO: can also create all links and fix some joints
    # TODO: SE(3) motion planner (like my SE(2) one) where some dimensions are fixed

    obstacle = create_box(w=SIZE, l=SIZE, h=SIZE, color=RED)
    obstacles = [obstacle]

    # body = create_cylinder(radius=0.025, height=0.1, color=GREEN)
    collision_id, visual_id = create_shape(get_cylinder_geometry(radius=0.025, height=0.1), color=apply_alpha(BLUE, 1))
    robot = create_flying_body(group, collision_id, visual_id)

    body_link = get_links(robot)[-1]
    joints = get_movable_joints(robot)
    joint_from_group = dict(zip(group, joints))
    print('joint_from_group: ', joint_from_group)
    # print(get_aabb(robot, body_link))
    # dump_body(robot, fixed=False)
    custom_limits = {joint_from_group[j]: l for j, l in CUSTOM_LIMITS.items()}

    initial_point = SIZE*np.array([-1., -1., 0])
    final_point = -initial_point
    initial_euler = np.zeros(3)
    add_line(initial_point, final_point, color=GREEN)

    initial_conf = np.concatenate([initial_point, initial_euler])
    resolutions = [0.01 for _ in range(3)] +  [np.pi/18 for _ in range(3)]
    final_conf = np.concatenate([final_point, initial_euler])

    set_joint_positions(robot, joints, initial_conf)

    path = plan_joint_motion(robot, joints, final_conf, obstacles=obstacles,
                             self_collisions=True, custom_limits=custom_limits, resolutions=resolutions,
                             coarse_waypoints=False)
    if path is None:
        disconnect()
        assert False, 'se3 planning fails!'

    for i, conf in enumerate(path):
        set_joint_positions(robot, joints, conf)
        point, quat = get_link_pose(robot, body_link)
        # euler = intrinsic_euler_from_quat(quat)
        draw_pose((point, quat), length=0.1)

        assert np.allclose(point, conf[:3], atol=1e-3, rtol=0)
        # assert np.allclose(quat, quat_from_euler(conf[3:]), atol=1e-1, rtol=0)

        wait_if_gui('Step: {}/{}'.format(i, len(path)))

    wait_if_gui('Finish?')
    disconnect()
