#!/usr/bin/env swift
// Composes "Before | After" comparison images from two same-size screenshots.
//
//   swift before_after.swift --before a.png --after b.png --out out.png
//                            [--crop x,y,w,h | --full] [--padding 60] [--gap 160] [--tolerance 0]
//
// Default: finds the rows that differ, groups them into bands separated by more than
// `--gap` unchanged rows, and writes one full-width image per band (out.png, or
// out-1.png, out-2.png ... when there are several). Coordinates are pixels, origin top-left.
// Exit codes: 0 written, 1 usage or I/O error, 2 no difference above tolerance in the region.

import CoreGraphics
import CoreText
import Foundation
import ImageIO
import UniformTypeIdentifiers

func fail(_ message: String, code: Int32 = 1) -> Never {
    FileHandle.standardError.write(Data((message + "\n").utf8))
    exit(code)
}

struct Bitmap {
    let width: Int
    let height: Int
    let image: CGImage
    let pixels: [UInt8] // RGBA, row 0 is the top row

    init(path: String) {
        let url = URL(fileURLWithPath: path) as CFURL
        guard let source = CGImageSourceCreateWithURL(url, nil),
              let image = CGImageSourceCreateImageAtIndex(source, 0, nil)
        else {
            fail("Cannot read image: \(path)")
        }

        let width = image.width
        let height = image.height
        var pixels = [UInt8](repeating: 0, count: width * height * 4)
        let drawn = pixels.withUnsafeMutableBytes { buffer -> Bool in
            guard let context = CGContext(
                data: buffer.baseAddress, width: width, height: height, bitsPerComponent: 8,
                bytesPerRow: width * 4, space: CGColorSpace(name: CGColorSpace.sRGB)!,
                bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue,
            ) else {
                return false
            }

            context.draw(image, in: CGRect(x: 0, y: 0, width: width, height: height))
            return true
        }
        guard drawn else {
            fail("Cannot decode image: \(path)")
        }

        self.width = width
        self.height = height
        self.image = image
        self.pixels = pixels
    }

    func rowDiffers(from other: Bitmap, row: Int, columns: Range<Int>, tolerance: Int) -> Bool {
        let start = (row * width + columns.lowerBound) * 4
        let end = (row * width + columns.upperBound) * 4
        for offset in start ..< end
            where abs(Int(pixels[offset]) - Int(other.pixels[offset])) > tolerance
        {
            return true
        }
        return false
    }
}

// MARK: - Arguments

var options: [String: String] = [:]
var flags: Set<String> = []
var arguments = Array(CommandLine.arguments.dropFirst())
let valueOptions: Set<String> = ["--before", "--after", "--out", "--crop", "--padding", "--gap", "--tolerance"]

while !arguments.isEmpty {
    let name = arguments.removeFirst()
    guard name.hasPrefix("--") else {
        fail("Unexpected argument: \(name)")
    }

    if name == "--full" {
        flags.insert(name)
    } else {
        guard valueOptions.contains(name) else {
            fail("Unknown option: \(name)")
        }
        guard !arguments.isEmpty else {
            fail("Missing value for \(name)")
        }

        options[name] = arguments.removeFirst()
    }
}

guard let beforePath = options["--before"], let afterPath = options["--after"], let outPath = options["--out"] else {
    fail(
        "Usage: before_after.swift --before a.png --after b.png --out out.png "
            + "[--crop x,y,w,h | --full] [--padding 60] [--gap 160] [--tolerance 0]",
    )
}

func integerOption(_ name: String, default fallback: Int, range: ClosedRange<Int>) -> Int {
    guard let value = Int(options[name] ?? String(fallback)), range.contains(value) else {
        fail("\(name) must be an integer in \(range)")
    }
    return value
}

let padding = integerOption("--padding", default: 60, range: 0 ... Int.max)
let gap = integerOption("--gap", default: 160, range: 0 ... Int.max)
let tolerance = integerOption("--tolerance", default: 0, range: 0 ... 255)
guard options["--crop"] == nil || !flags.contains("--full") else {
    fail("Use either --crop or --full, not both")
}

let before = Bitmap(path: beforePath)
let after = Bitmap(path: afterPath)

guard before.width == after.width, before.height == after.height else {
    fail(
        "Screenshots differ in size (\(before.width)x\(before.height) vs \(after.width)x\(after.height)); "
            + "use the same device.",
    )
}

let width = before.width
let height = before.height

// MARK: - Regions

var regions: [CGRect] = []

if let crop = options["--crop"] {
    let fields = crop.split(separator: ",", omittingEmptySubsequences: false)
    let parts = fields.compactMap { Int($0) }
    guard fields.count == 4, parts.count == 4, parts[2] > 0, parts[3] > 0 else {
        fail("--crop expects x,y,w,h in pixels")
    }

    let rect = CGRect(x: parts[0], y: parts[1], width: parts[2], height: parts[3])
        .intersection(CGRect(x: 0, y: 0, width: width, height: height))
    guard !rect.isEmpty else {
        fail("--crop is outside the screenshot")
    }

    let columns = Int(rect.minX) ..< Int(rect.maxX)
    guard (Int(rect.minY) ..< Int(rect.maxY)).contains(where: {
        before.rowDiffers(from: after, row: $0, columns: columns, tolerance: tolerance)
    }) else {
        fail("No pixels exceed the tolerance in the selected crop.", code: 2)
    }

    regions = [rect]
} else {
    let changedRows = (0 ..< height).filter {
        before.rowDiffers(from: after, row: $0, columns: 0 ..< width, tolerance: tolerance)
    }
    guard let first = changedRows.first else {
        fail("No pixels exceed the tolerance in the screenshots.", code: 2)
    }

    if flags.contains("--full") {
        regions = [CGRect(x: 0, y: 0, width: width, height: height)]
    } else {
        var bands: [(Int, Int)] = [(first, first)]
        for row in changedRows.dropFirst() {
            if row - bands[bands.count - 1].1 > gap {
                bands.append((row, row))
            } else {
                bands[bands.count - 1].1 = row
            }
        }
        regions = bands.map { band in
            let top = band.0 - min(band.0, padding)
            let bottom = band.1 + 1 + min(height - band.1 - 1, padding)
            return CGRect(x: 0, y: top, width: width, height: bottom - top)
        }
    }
}

// MARK: - Composition

let gray = CGColor(gray: 0.5, alpha: 1)

func drawLabel(_ text: String, in context: CGContext, panelX: CGFloat, canvasHeight: CGFloat, scale: CGFloat) {
    let font = CTFontCreateWithName("HelveticaNeue" as CFString, 44 * scale, nil)
    let attributes: [NSAttributedString.Key: Any] = [
        NSAttributedString.Key(kCTFontAttributeName as String): font,
        NSAttributedString.Key(kCTForegroundColorAttributeName as String): CGColor(gray: 1, alpha: 1),
    ]
    let line = CTLineCreateWithAttributedString(NSAttributedString(string: text, attributes: attributes))
    let bounds = CTLineGetBoundsWithOptions(line, .useOpticalBounds)
    let inset = 10 * scale
    let box = CGRect(
        x: panelX + 14 * scale, y: canvasHeight - 6 * scale - (bounds.height + inset),
        width: bounds.width + inset * 2, height: bounds.height + inset,
    )
    context.setFillColor(gray)
    context.fill(box)
    context.textPosition = CGPoint(x: box.minX + inset - bounds.minX, y: box.minY + inset / 2 - bounds.minY)
    CTLineDraw(line, context)
}

func write(region: CGRect, to path: String) {
    let panelWidth = Int(region.width)
    let panelHeight = Int(region.height)
    let divider = max(8, width / 50)
    let canvasWidth = panelWidth * 2 + divider
    guard let context = CGContext(
        data: nil, width: canvasWidth, height: panelHeight, bitsPerComponent: 8, bytesPerRow: 0,
        space: CGColorSpace(name: CGColorSpace.sRGB)!, bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue,
    ) else {
        fail("Cannot create canvas")
    }

    context.setFillColor(gray)
    context.fill(CGRect(x: 0, y: 0, width: canvasWidth, height: panelHeight))
    let scale = min(1, CGFloat(panelWidth) / 1206)
    for (index, bitmap) in [before, after].enumerated() {
        guard let cropped = bitmap.image.cropping(to: region) else {
            fail("Cannot crop region \(region)")
        }

        let panelX = CGFloat(index * (panelWidth + divider))
        context.draw(cropped, in: CGRect(x: panelX, y: 0, width: CGFloat(panelWidth), height: CGFloat(panelHeight)))
        drawLabel(
            index == 0 ? "Before" : "After", in: context, panelX: panelX,
            canvasHeight: CGFloat(panelHeight), scale: scale,
        )
    }
    let url = URL(fileURLWithPath: path) as CFURL
    guard let image = context.makeImage(),
          let destination = CGImageDestinationCreateWithURL(url, UTType.png.identifier as CFString, 1, nil)
    else {
        fail("Cannot write \(path)")
    }

    CGImageDestinationAddImage(destination, image, nil)
    guard CGImageDestinationFinalize(destination) else {
        fail("Cannot write \(path)")
    }

    print("\(path)  crop=\(Int(region.minX)),\(Int(region.minY)),\(panelWidth),\(panelHeight)")
}

if regions.count == 1 {
    write(region: regions[0], to: outPath)
} else {
    let url = URL(fileURLWithPath: outPath)
    let stem = url.deletingPathExtension().path
    for (index, region) in regions.enumerated() {
        write(region: region, to: "\(stem)-\(index + 1).png")
    }
}
