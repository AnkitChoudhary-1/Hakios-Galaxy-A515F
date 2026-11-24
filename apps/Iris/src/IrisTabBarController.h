// IrisTabBarController.h - Custom bottom navigation bar for Iris
#import <UIKit/UIKit.h>

typedef NS_ENUM(NSInteger, IrisTabItem) {
    IrisTabItemHome = 0,
    IrisTabItemExplore,
    IrisTabItemCreate,
    IrisTabItemActivity,
    IrisTabItemProfile
};

@interface IrisTabBarController : UIViewController

@property (nonatomic, assign) IrisTabItem selectedTab;
@property (nonatomic, strong, readonly) NSArray<UIViewController *> *viewControllers;

- (instancetype)initWithViewControllers:(NSArray<UIViewController *> *)viewControllers;
- (void)switchToTab:(IrisTabItem)tab;

@end
