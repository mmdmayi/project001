# import maya.api.OpenMaya as om2
# import maya.api.OpenMayaAnim as oma2
# import time
#
#
# def get_skin_cluster2(dag_path):
#     it = om2.MItDependencyGraph(
#         dag_path.node(),
#         om2.MItDependencyGraph.kUpstream,
#         om2.MItDependencyGraph.kPlugLevel
#     )
#     while not it.isDone():
#         node = it.currentNode()
#         if node.hasFn(om2.MFn.kSkinClusterFilter):
#             return oma2.MFnSkinCluster(node)
#         it.next()
#     return None
#
#
# def smooth_skin_weights_on_selected_vertices_api2(blend_value=1.0):
#     start_time = time.time()
#
#     selection = om2.MGlobal.getActiveSelectionList()
#     if selection.length() == 0:
#         om2.MGlobal.displayError(u"请先选择需要平滑的顶点")
#         return
#
#     dag_path, comp = selection.getComponent(0)
#     dag_path = dag_path.extendToShape()
#     skin_cluster = get_skin_cluster2(dag_path)
#     if not skin_cluster:
#         om2.MGlobal.displayError(u"没有找到skinCluster")
#         return
#
#     # 获取选中的顶点
#     sel_fn = om2.MFnSingleIndexedComponent(comp)
#     sel_indices = sel_fn.getElements()
#
#     om2.MGlobal.displayInfo(f"开始处理 {len(sel_indices)} 个顶点...")
#
#     # 创建网格迭代器
#     vtx_iter = om2.MItMeshVertex(dag_path)
#
#     all_connected = {}
#
#     all_infDags = skin_cluster.influenceObjects()
#     all_inf_indices = [skin_cluster.indexForInfluenceObject(obj) for obj in all_infDags]
#
#     # 创建影响物索引数组
#     inf_indices = om2.MIntArray(all_inf_indices)
#     inf_count = len(inf_indices)
#
#     om2.MGlobal.displayInfo(f"总骨骼数: {inf_count}")
#
#     BATCH_SIZE = 500  # 每批处理的顶点数
#     total_batches = (len(sel_indices) + BATCH_SIZE - 1) // BATCH_SIZE
#
#     for batch_idx in range(total_batches):
#         batch_start = batch_idx * BATCH_SIZE
#         batch_end = min(batch_start + BATCH_SIZE, len(sel_indices))
#         batch_vertices = sel_indices[batch_start:batch_end]
#
#         om2.MGlobal.displayInfo(f"处理批次 {batch_idx + 1}/{total_batches} ({batch_end - batch_start} 个顶点)...")
#
#         for vtx in batch_vertices:
#             if vtx not in all_connected:
#                 vtx_iter.setIndex(vtx)
#                 all_connected[vtx] = vtx_iter.getConnectedVertices()
#
#         for vtx in batch_vertices:
#             # 获取相邻顶点
#             surr_indices = all_connected[vtx]
#             if not surr_indices or blend_value <= 0.0:
#                 continue
#
#             vtx_comp = om2.MFnSingleIndexedComponent().create(om2.MFn.kMeshVertComponent)
#             om2.MFnSingleIndexedComponent(vtx_comp).addElement(vtx)
#
#             old_weights = skin_cluster.getWeights(dag_path, vtx_comp, inf_indices)
#
#             neighbor_comp = om2.MFnSingleIndexedComponent().create(om2.MFn.kMeshVertComponent)
#             for n_idx in surr_indices:
#                 om2.MFnSingleIndexedComponent(neighbor_comp).addElement(n_idx)
#
#             neighbor_weights = skin_cluster.getWeights(dag_path, neighbor_comp, inf_indices)
#
#             avg_weights = [0.0] * inf_count
#             for n_idx in range(len(surr_indices)):
#                 for inf_idx in range(inf_count):
#                     avg_weights[inf_idx] += neighbor_weights[n_idx * inf_count + inf_idx]
#
#             new_weights = om2.MDoubleArray(old_weights)
#
#             for i in range(inf_count):
#                 avg_weight = avg_weights[i] / len(surr_indices)
#                 new_weights[i] = (1.0 - blend_value) * old_weights[i] + blend_value * avg_weight
#
#             skin_cluster.setWeights(dag_path, vtx_comp, inf_indices, new_weights, False)
#
#     end_time = time.time()
#     elapsed = end_time - start_time
#     om2.MGlobal.displayInfo(f"权重平滑完成。处理了 {len(sel_indices)} 个顶点，耗时: {elapsed:.2f} 秒")
#
# # smooth_skin_weights_on_selected_vertices_api2(blend_value=0.75)
import maya.api.OpenMaya as om2
import maya.api.OpenMayaAnim as oma2
import time
import numpy as np
def get_skin_cluster2(dag_path):
    it = om2.MItDependencyGraph(
        dag_path.node(),
        om2.MItDependencyGraph.kUpstream,
        om2.MItDependencyGraph.kPlugLevel
    )
    while not it.isDone():
        node = it.currentNode()
        if node.hasFn(om2.MFn.kSkinClusterFilter):
            return oma2.MFnSkinCluster(node)
        it.next()
    return None


def smooth_skin_weights_on_selected_vertices_api2(blend_value=1.0):
    start_time = time.time()

    selection = om2.MGlobal.getActiveSelectionList()
    if selection.length() == 0:
        om2.MGlobal.displayError(u"请先选择需要平滑的顶点")
        return

    dag_path, comp = selection.getComponent(0)
    dag_path = dag_path.extendToShape()
    skin_cluster = get_skin_cluster2(dag_path)
    if not skin_cluster:
        om2.MGlobal.displayError(u"没有找到skinCluster")
        return

    sel_fn = om2.MFnSingleIndexedComponent(comp)
    sel_indices = sel_fn.getElements()

    om2.MGlobal.displayInfo(f"开始处理 {len(sel_indices)} 个顶点...")

    all_infDags = skin_cluster.influenceObjects()
    all_inf_indices = [skin_cluster.indexForInfluenceObject(obj) for obj in all_infDags]

    inf_indices = om2.MIntArray(all_inf_indices)
    inf_count = len(inf_indices)

    mesh_fn = om2.MFnMesh(dag_path)
    vtx_iter = om2.MItMeshVertex(dag_path)

    om2.MGlobal.displayInfo("预处理顶点连接信息...")
    connected_verts = {}
    for vtx in sel_indices:
        vtx_iter.setIndex(vtx)
        connected_verts[vtx] = vtx_iter.getConnectedVertices()

    om2.MGlobal.displayInfo("批量获取权重信息...")

    all_comp = om2.MFnSingleIndexedComponent().create(om2.MFn.kMeshVertComponent)
    for vtx in sel_indices:
        om2.MFnSingleIndexedComponent(all_comp).addElement(vtx)

    all_weights = skin_cluster.getWeights(dag_path, all_comp, inf_indices)

    np_weights = np.array(all_weights).reshape(len(sel_indices), inf_count)

    vtx_index_map = {v: i for i, v in enumerate(sel_indices)}

    new_weights_np = np.copy(np_weights)

    om2.MGlobal.displayInfo("计算平均权重...")
    for i, vtx in enumerate(sel_indices):
        neighbors = connected_verts[vtx]
        if not neighbors or blend_value <= 0.0:
            continue

        neighbor_indices = []
        for n in neighbors:
            if n in vtx_index_map:
                neighbor_indices.append(vtx_index_map[n])

        if not neighbor_indices:
            continue

        avg_weights = np.mean(np_weights[neighbor_indices], axis=0)

        new_weights_np[i] = (1.0 - blend_value) * np_weights[i] + blend_value * avg_weights

    om2.MGlobal.displayInfo("应用新权重...")
    for i, vtx in enumerate(sel_indices):
        vtx_comp = om2.MFnSingleIndexedComponent().create(om2.MFn.kMeshVertComponent)
        om2.MFnSingleIndexedComponent(vtx_comp).addElement(vtx)

        new_weights = om2.MDoubleArray(new_weights_np[i].tolist())

        skin_cluster.setWeights(dag_path, vtx_comp, inf_indices, new_weights, False)

    end_time = time.time()
    elapsed = end_time - start_time
    om2.MGlobal.displayInfo(f"权重平滑完成。处理了 {len(sel_indices)} 个顶点，耗时: {elapsed:.2f} 秒")

# import maya.api.OpenMaya as om2
# import maya.api.OpenMayaAnim as oma2
# def get_skin_cluster2(dag_path):
#     it = om2.MItDependencyGraph(
#         dag_path.node(),
#         om2.MItDependencyGraph.kUpstream,
#         om2.MItDependencyGraph.kPlugLevel
#     )
#     while not it.isDone():
#         node = it.currentNode()
#         if node.hasFn(om2.MFn.kSkinClusterFilter):
#             return oma2.MFnSkinCluster(node)
#         it.next()
#     return None
#
# def safe_smooth_skin_weights(blend_value=1.0):
#     selection = om2.MGlobal.getActiveSelectionList()
#     dag_path, comp = selection.getComponent(0)
#     dag_path = dag_path.extendToShape()
#     skin_cluster = get_skin_cluster2(dag_path)
#     if not skin_cluster:
#         om2.MGlobal.displayError(u"没有找到skinCluster")
#         return
#
#     sel_fn = om2.MFnSingleIndexedComponent(comp)
#     sel_indices = sel_fn.getElements()
#     mesh_fn = om2.MFnMesh(dag_path)
#     infs = skin_cluster.influenceObjects()
#     #all_infDags = skin_cluster.influenceObjects()
#     all_inf_indices = [skin_cluster.indexForInfluenceObject(obj) for obj in infs]
#
#     inf_indices = om2.MIntArray(all_inf_indices)
#     print(inf_indices)
#     inf_count = len(all_inf_indices)
#     for vtx in sel_indices:
#         vtx_comp = om2.MFnSingleIndexedComponent().create(om2.MFn.kMeshVertComponent)
#         om2.MFnSingleIndexedComponent(vtx_comp).addElement(vtx)
#         old_weights, _ = skin_cluster.getWeights(dag_path, vtx_comp)
#
#         vtx_iter = om2.MItMeshVertex(dag_path)
#         vtx_iter.setIndex(vtx)
#         surr_indices = vtx_iter.getConnectedVertices()
#         # 跳过异常点
#         surr_indices = [s for s in surr_indices if s < mesh_fn.numVertices]
#         surr_count = len(surr_indices)
#         if surr_count == 0:
#             continue
#
#         surr_comp = om2.MFnSingleIndexedComponent().create(om2.MFn.kMeshVertComponent)
#         om2.MFnSingleIndexedComponent(surr_comp).addElements(surr_indices)
#         surr_weights, _ = skin_cluster.getWeights(dag_path, surr_comp)
#
#         new_weights = []
#         for i in range(inf_count):
#             # 仅用有效邻居做平均
#             avg = sum(surr_weights[j] for j in range(i, len(surr_weights), inf_count)) / surr_count
#             blended = avg * blend_value + old_weights[i] * (1.0 - blend_value)
#             new_weights.append(blended)
#
#         skin_cluster.setWeights(
#             dag_path,
#             vtx_comp,
#             inf_indices,
#             new_weights,
#             False
#         )
#
#     om2.MGlobal.displayInfo(u"权重平滑完成（极限安全）")
#
# #safe_smooth_skin_weights(blend_value=1.0)

