#!/usr/bin/env python
import cv2
import cv2.aruco as aruco
import keyboard
import imutils
import math
import numpy as np
import rospy
from std_msgs.msg import String, Int16
from sensor_msgs.msg import NavSatFix

cap = cv2.VideoCapture(0)
# Empty list initialize to store point objects
bounds = []

boundsDefined = False
topLeftDefined = False
bottomRightDefined = False
originDefined = False
overlay = None

j = 0

font = cv2.FONT_HERSHEY_SIMPLEX
fontScale = 1
fontColor = (0, 0, 0)
lineType = 2

cX, cY = 0, 0

loc_pub = rospy.Publisher('/location', NavSatFix, queue_size=10)
heading_pub = rospy.Publisher('/heading', Int16, queue_size=10)

mat_pub = rospy.Publisher('/mat_info', String, queue_size=10)
dest_pub = rospy.Publisher('/destination', NavSatFix, queue_size=10)

rospy.init_node('open_cv', anonymous=True)
rate = rospy.Rate(1)  # 1Hz

# -- Declare Global variables
hsv2 = [332, 333, 137, 153, 255, 255]  # 2x2
hsv1 = [52, 53, 156, 200, 255, 255]  # 2x4


class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y


class Detection:
    def __init__(self):
        self.robotCenter = Point(0, 0)
        self.robotHeading = None
        self.numberOfPackages = None
        self.packageLocation = Point(0, 0)
        self.points = []
        self.blockLocations = []
        self.pointsCtr = 0
        self.numberOfPoints = 0
        self.realWidth = 200.0  # 200 cm
        self.pixelWidth = 0.0
        self.pixelHeight = 0.0
        self.absCenter = Point(0, 0)
        self.correctionRatio = 0.9333
        self.scale = 0.0
        self.previousPoint = Point(0, 0)
        self.distanceTravelled = 0

    def calculateScale(self):
        self.scale = self.realWidth / self.pixelWidth

    def fillPoints(self):
        self.numberOfPoints = len(self.points)

    def calculateDistance(self):
        distance = 0.0
        for i in range(len(self.points)):
            if i is not 0:
                distance = distance + math.hypot(self.scale * (self.points[i].x - self.points[i - 1].x),
                                                 self.scale * (self.points[i].y - self.points[i - 1].y))
        self.distanceTravelled = int(distance)

    def sendLocations(self):
        homeLocation = Point((self.pixelHeight * 0.05 + bounds[0].y) * self.scale,
                             (self.pixelWidth * 0.05 + bounds[0].x) * self.scale)

        bigLocation = Point((self.pixelHeight * 0.975 + bounds[0].y) * self.scale,
                            (self.pixelWidth * 0.975 + bounds[0].x) * self.scale)

        smallLocation = Point((self.pixelHeight * 0.975 + bounds[0].y) * self.scale,
                              (self.pixelWidth * 0.025 + bounds[0].x) * self.scale)

        mat_pub.publish(f"{homeLocation},{smallLocation},{bigLocation}")
        print(f"{homeLocation.x},{homeLocation.y};{smallLocation.x},{smallLocation.y};{bigLocation.x},{bigLocation.y}")


# Function callback to handle mouse requests
def draw_circle(event, xCoord, yCoord, flags, param):
    global line, topLeftDefined, bottomRightDefined, boundsDefined
    # Draw circles when left mouse button is clicked
    if event == cv2.EVENT_LBUTTONDOWN:
        if not topLeftDefined:
            topLeft = Point(xCoord, yCoord)
            bounds.append(topLeft)
            topLeftDefined = True
        elif not bottomRightDefined and topLeftDefined:
            bottomRight = Point(xCoord, yCoord)
            bounds.append(bottomRight)
            bottomRightDefined = True
            boundsDefined = True
        else:
            print(f"Circle at {xCoord}, {yCoord}, Points size: {len(detect.points) + 1}")
            click = Point(xCoord, yCoord)
            detect.points.append(click)

    # Clears the points list on right mouse button click
    elif event == cv2.EVENT_RBUTTONDOWN:
        detect.points.clear()
        detect.distanceTravelled = 0
    elif event == cv2.EVENT_MOUSEWHEEL:
        if line:
            line = False
        else:
            line = True
        pass


# Sets a name to the window
cv2.namedWindow('Transparency')
# Sets up mouse callback to register mouse events
cv2.setMouseCallback("Transparency", draw_circle)

# Initialize global navigation class object
detect = Detection()


def calculateAvgPoint(someList):
    xPoint = 0
    yPoint = 0
    for element in someList:
        xPoint = xPoint + element.x
        yPoint = yPoint + element.y

    return Point(int(xPoint / len(someList)), int(yPoint / len(someList)))


cam_matrix = np.array([[1.0e+04, 0.00000000e+00, 1.22400000e+03],
                       [0.00000000e+00, 1.0e+04, 1.02400000e+03],
                       [0.00000000e+00, 0.00000000e+00, 1.00000000e+00]])
dist_coeffs = np.array([[0.],
                        [0.],
                        [0.],
                        [0.],
                        [0.],
                        [0.],
                        [0.],
                        [0.],
                        [0.],
                        [0.],
                        [0.],
                        [0.],
                        [0.],
                        [0.]])
marker_length = 30.00  # some arbitraty value

point = NavSatFix()
destination = NavSatFix()
head = Int16()


def Detect_Lego(frame, calibrationMode=True):
    # Declare local variables
    x = y = lower = upper = 0

    # Convert image to HSV
    imgHSV = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    # Set values
    # if block == 1:
    lower = np.array([hsv1[0], hsv1[1], hsv1[2]])
    upper = np.array([hsv1[3], hsv1[4], hsv1[5]])
    # elif block == 2:
    lower2 = np.array([hsv2[0], hsv2[1], hsv2[2]])
    upper2 = np.array([hsv2[3], hsv2[4], hsv2[5]])
    mask = cv2.inRange(imgHSV, lower, upper)
    mask2 = cv2.inRange(imgHSV, lower2, upper2)

    # Setup SimpleBlobDetector parameters.
    params = cv2.SimpleBlobDetector_Params()

    # Filter by Area.
    params.filterByArea = True
    params.minArea = 90
    params.maxArea = 8000

    # Filter by Circularity
    params.filterByCircularity = False
    # params.minCircularity = 0.1

    # Filter by Convexity
    params.filterByConvexity = False
    # params.minConvexity = 0.1

    # Filter by Inertia
    params.filterByInertia = False
    # params.minInertiaRatio = 0.1

    # Set up the detector with default parameters.
    detector = cv2.SimpleBlobDetector_create(params)

    reversemask = 255 - mask
    blur = cv2.GaussianBlur(reversemask, (9, 9), 0)
    reversemask2 = 255 - mask2
    blur2 = cv2.GaussianBlur(reversemask2, (9, 9), 0)

    # Detect blobs.
    keypoints = detector.detect(blur)
    keypoints2 = detector.detect(blur2)

    if calibrationMode:
        return keypoints, reversemask, keypoints2, reversemask2
    else:
        return keypoints, keypoints2


def runDetection():
    shot_pressed = 0
    was_pressed = False
    dimensions = False
    line = False
    locations_published = False
    blocksAcquired = False
    listLength = 0
    contour_list = []
    blockCheckCtr = 0
    checkLimit = 2
    lastPoint = Point(0, 0)

    while True:
        # Capture frame-by-frame
        ret, frame = cap.read()

        scale_percent = 100  # percent of original size
        width = int(frame.shape[1] * scale_percent / 100)
        height = int(frame.shape[0] * scale_percent / 100)
        dim = (width, height)
        # resize image
        resized = cv2.resize(frame, dim, interpolation=cv2.INTER_AREA)

        # Converts from Red, Green, Blue, Alpha color space to simple RGB
        feed = cv2.cvtColor(resized, cv2.COLOR_RGBA2RGB)
        overlay = feed.copy()

        # if the view has been boundsDefined: apply new bounds to overlay and feed layer
        # else just make a copy of the feed to draw on
        if boundsDefined:
            cv2.rectangle(overlay, (bounds[0].x, bounds[0].y), (bounds[1].x, bounds[1].y), (255, 0, 0), 2)

            # overlay = resized[bounds[0].y:bounds[1].y, bounds[0].x:bounds[1].x]
            # feed = feed[bounds[0].y:bounds[1].y, bounds[0].x:bounds[1].x]
            detect.pixelWidth = bounds[1].x - bounds[0].x
            detect.pixelHeight = bounds[1].y - bounds[0].y
            detect.calculateScale()
            if not locations_published:
                detect.sendLocations()
                locations_published = True

        # convert to grayscale

        grayscale = cv2.cvtColor(feed, cv2.COLOR_BGR2GRAY)

        # Applies blur to straighten line zigzags
        median = cv2.medianBlur(grayscale, 5)

        hsv = cv2.cvtColor(feed, cv2.COLOR_BGR2HSV)

        # converts to threshold
        thresh = cv2.threshold(grayscale, 60, 255, cv2.THRESH_BINARY)[1]

        # perform edge detection
        edges = cv2.Canny(median, 30, 100)

        # set opacity of objects drawn on overlay
        opacity = 0.5

        # Once boundsDefined view has been boundsDefined, run detection for circles and triangles
        if boundsDefined:
            aruco_dict = aruco.Dictionary_get(aruco.DICT_6X6_250)
            parameters = aruco.DetectorParameters_create()
            corners, ids, rejectedImgPoints = aruco.detectMarkers(grayscale, aruco_dict, parameters=parameters)
            rvec, tvec, _ = aruco.estimatePoseSingleMarkers(corners, marker_length, cam_matrix, dist_coeffs)

            if corners is not None:
                for i in range(len(corners)):
                    x = (corners[i - 1][0][0][0] + corners[i - 1][0][1][0] + corners[i - 1][0][2][0] +
                         corners[i - 1][0][3][
                             0]) / 4
                    y = (corners[i - 1][0][0][1] + corners[i - 1][0][1][1] + corners[i - 1][0][2][1] +
                         corners[i - 1][0][3][
                             1]) / 4
                    rotM = np.zeros(shape=(3, 3))
                    cv2.Rodrigues(rvec[i - 1], rotM, jacobian=0)
                    ypr = cv2.RQDecomp3x3(rotM)
                    detect.robotCenter = Point(x - bounds[0].x, y - bounds[0].y)
                    if ypr[0][2] < 0:
                        detect.robotHeading = 360 + ypr[0][2] - 90

                    elif 0 < ypr[0][2] < 90:
                        detect.robotHeading = 270 + ypr[0][2]
                    else:
                        detect.robotHeading = ypr[0][2] - 90

                    if detect.robotHeading is not None and detect.robotCenter is not None:
                        point.latitude = int(detect.robotCenter.y * detect.scale)
                        point.longitude = int(detect.robotCenter.x * detect.scale)
                        head.data = int(detect.robotHeading)
                        loc_pub.publish(point)
                        heading_pub.publish(head)
                        cv2.putText(overlay, f"X,Y: {int(detect.robotCenter.y * detect.scale)} cm,"
                                             f" {int(detect.robotCenter.x * detect.scale)} cm",
                                    (int(bounds[1].x - 300), int(bounds[0].y)),
                                    font, 1, (0, 0, 0), 2)
                        cv2.putText(overlay, f"Heading: {int(detect.robotHeading)} deg",
                                    (int(bounds[1].x - 300), int(bounds[0].y + 40)),
                                    font, 1, (0, 0, 0), 2)

            overlay = aruco.drawDetectedMarkers(overlay, corners, ids)

        # Loops through points list a draws them on overlay
        for i in range(len(detect.points)):
            cv2.circle(overlay, (detect.points[i].x, detect.points[i].y), 5, (0, 0, 255), -1)
            if line:
                if i > 0:
                    cv2.line(overlay,
                             (detect.points[i - 1].x,
                              detect.points[i - 1].y),
                             (detect.points[i].x,
                              detect.points[i].y),
                             (255, 0, 0), 3, -1)

        # Blends the two layers
        added_image = cv2.addWeighted(overlay, opacity, feed, 1 - opacity, 0, feed)

        # display result (press 'q' to quit):
        cv2.imshow('Transparency', added_image)

        if not dimensions:
            print(cv2.getWindowImageRect("Transparency"))
            dimensions = True
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

        if keyboard.is_pressed('del'):
            if not was_pressed:
                if len(detect.points) is not 0:
                    del detect.points[-1]
                shot_pressed += 1
                was_pressed = True
            else:
                was_pressed = False
        elif keyboard.is_pressed('1'):
            if not was_pressed:
                detect.fillPoints()
                # sendPointsArray()
                detect.calculateDistance()
                shot_pressed += 1
                was_pressed = True
            else:
                was_pressed = False
        elif keyboard.is_pressed('2'):
            if not was_pressed:
                if line:
                    line = False
                else:
                    line = True
                pass
                was_pressed = True

            else:
                was_pressed = False
        elif keyboard.is_pressed('3'):
            if not was_pressed:
                detect.points.clear()
                detect.distanceTravelled = 0
            else:
                was_pressed = False

        elif keyboard.is_pressed('n'):
            if not was_pressed:
                if (len(detect.points)) is not 0:
                    destination.latitude = (detect.points[0].y - bounds[0].y) * detect.scale
                    destination.longitude = (detect.points[0].x - bounds[0].x) * detect.scale
                    dest_pub.publish(destination)
                    detect.points.clear()
                was_pressed = True
            else:
                was_pressed = False


if __name__ == '__main__':
    try:
        runDetection()

    except rospy.ROSInterruptException:
        pass

# When everything done, release the capture
cap.release()
cv2.destroyAllWindows()
