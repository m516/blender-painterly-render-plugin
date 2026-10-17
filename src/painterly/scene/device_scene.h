/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#pragma once

/* PainterlyDeviceScene: the host owner of everything the kernel reads, the counterpart of Cycles'
 * DeviceScene at painterly scale. It holds KernelPainterlyData, the arrays that
 * PainterlyGlobalsCPU points at (painterly/kernel/globals.h) and the Embree scene
 * (painterly/bvh/embree.h), which is built only when the scene has triangles.
 * PainterlyScene::device_update (device_scene.cpp) is the only writer. */

#include <cstdint>
#include <vector>

#include "painterly/bvh/embree.h"
#include "painterly/kernel/globals.h"
#include "painterly/kernel/types.h"

CCL_NAMESPACE_BEGIN

class PainterlyScene;

class PainterlyDeviceScene {
 public:
  PainterlyDeviceScene() = default;
  /* Frees the Embree scene. */
  ~PainterlyDeviceScene();
  /* Non-copyable: globals_ points into this object's arrays. */
  PainterlyDeviceScene(const PainterlyDeviceScene &) = delete;
  PainterlyDeviceScene &operator=(const PainterlyDeviceScene &) = delete;

  /* The kernel data and the arrays, in the layout of painterly/kernel/globals.h. */
  KernelPainterlyData data{};
  std::vector<KernelPainterlyAnalytic> analytic;
  std::vector<KernelPainterlyMaterial> materials;
  std::vector<KernelPainterlyLobe> lobes;
  std::vector<KernelPainterlySun> suns;
  std::vector<KernelPainterlyObject> objects;
  std::vector<KernelPainterlyMesh> meshes;
  std::vector<int> tri_material;
  std::vector<float> tri_corner_normals;

  /* The read-only view of this device scene for one render. Valid until the next device_update or
   * until this object is destroyed: it points into the vectors above. */
  PainterlyGlobalsCPU globals() const;

  /* Releases the Embree scene, if any. */
  void clear_bvh();

 private:
  friend class PainterlyScene;

  /* Takes ownership of `scene` (which may be null) after releasing the previous one. */
  void set_bvh(PainterlyEmbreeScene *scene);
  /* Points globals_ at data and at every array, with its size. An empty array gives a null
   * pointer, as PainterlyGlobalsCPU's comments require. Call it after the last change to the size
   * of an array, because a resize may move the elements. */
  void bind_globals();

  template<typename T> static const T *array_or_null(const std::vector<T> &values)
  {
    return values.empty() ? nullptr : values.data();
  }

  PainterlyEmbreeScene *bvh_ = nullptr;
  PainterlyGlobalsCPU globals_{};
};

CCL_NAMESPACE_END
