#-------------------------------------------------
#
# smallpaint by karoly zsolnai - zsolnai@cg.tuwien.ac.at
#
# render, modify, create new scenes, tinker around, and most of all:
# have fun!
#
# This program is used as an educational learning tool on the Rendering
# course at TU Wien. Course webpage:
# http://cg.tuwien.ac.at/courses/Rendering/
#
# This UI serves as an educational learning tool to see the progressions
# and experience the different renderes with different input.
# created by Michael Oppitz  - e1227129@student.tuwien.ac.at
#
#-------------------------------------------------

QT       += core gui

greaterThan(QT_MAJOR_VERSION, 4): QT += widgets

TARGET = Smallpaint
TEMPLATE = app

QMAKE_CXXFLAGS += -openmp

LIBS += -openmp

SOURCES += main.cpp \
    mainwindow.cpp \
    ../smallpaint_fixed/smallpaint_fixed.cpp \
    ../smallpaint_painterly/smallpaint_painterly.cpp \
    ../smallpaint_bvh/constants.cpp \
    ../smallpaint_bvh/smallpaint_bvh.cpp \
    ../smallpaint_smallmedia/smallpaint_smallmedia.cpp \
    ../smallpaint_pssmlt/smallpaint_pssmlt.cpp \
    mainrenderdistributor.cpp \
    testwindow.cpp \
    helperfunctions.cpp \
    ../smallpaint_ppm/smallpaint_ppm.cpp \
    image.cpp \
    ../smallpaint_vrl/smallpaint_vrl.cpp

HEADERS  += \
    mainwindow.h \
    main.h \
    ../smallpaint_bvh/AABB.hpp \
    ../smallpaint_bvh/constants.hpp \
    ../smallpaint_bvh/Ray.hpp \
    ../smallpaint_bvh/Vec.hpp \
    ../smallpaint_smallmedia/smallmedia.hpp \
    renderfunctions.h \
    scenegeometries.h \
    sceneGeometries.h \
    testwindow.h \
    helperfunctions.h \
    image.h \
    ../smallpaint_vrl/smallpaint_vrl_distanceFunctions.h \
    ../smallpaint_vrl/smallpaint_vrl_tests.h

FORMS    += \
    mainwindow.ui \
    testwindow.ui

RESOURCES = resources.qrc \
    resources.qrc

CONFIG -= debug_and_release debug_and_release_target

